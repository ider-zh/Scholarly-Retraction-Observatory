"""Finish all-Work statistics and analytical caches after verified graph benchmarks."""

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / 'disruption/src'))
from cache_foundation import atomic_json, digest_file, digest_json
from disruption.advance import resources


def verify_coverage(graph, annual, analytical, foundation):
    expected = foundation['rows']
    if graph['status'] != 'complete' or graph['node_count'] != expected:
        raise ValueError('Graph does not cover the completed foundation')
    if (not annual['complete'] or annual['scope'] != 'all_graph_works'
            or annual['requested_focal_count'] != expected or annual['graph_work_count'] != expected
            or sum(part['rows'] for part in annual['partitions']) != expected):
        raise ValueError('All-Work annual coverage incomplete')
    if (not analytical['complete'] or analytical['scope'] != 'all_graph_works'
            or analytical['focal_rows'] != expected or analytical['window_rows'] != 8 * expected
            or len(analytical['partitions']) != len(annual['partitions'])):
        raise ValueError('Analytical coverage incomplete')
    return expected


def run(args):
    prerequisite = args.prerequisite.resolve()
    parent = json.loads((prerequisite / 'state.json').read_text())
    foundation = Path(parent['foundation'])
    foundation_meta = json.loads((foundation / 'run.json').read_text())
    root = args.artifact_root.resolve()
    if not root.is_relative_to(Path('/mnt/hg02')) or not prerequisite.is_relative_to(root) or not foundation.is_relative_to(root):
        raise ValueError('All production artifacts must share the guarded /mnt/hg02 root')
    engine = args.engine.resolve()
    sources = {name: digest_file(PROJECT / 'disruption' / name) for name in
               ('full_run.py', 'advance.py', 'src/bulk_results.py', 'src/window_results.py')}
    config = {'prerequisite_job': str(prerequisite), 'engine_sha256': digest_file(engine),
              'foundation_config_sha256': foundation_meta['config_sha256'],
              'source_sha256': sources, 'partition_size': args.partition_size}
    output = root / 'full-runs' / digest_json(config)
    output.mkdir(parents=True, exist_ok=True)
    lock = (output / '.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = {'status': 'running', 'stage': 'await_benchmark', 'config': config,
             'foundation': str(foundation), 'workers': args.workers, 'export_workers': args.export_workers,
             'batch_size': args.batch_size, 'goal': 'all_graph_works_and_dual_window_analytical_cache'}

    def save():
        state['updated_at'] = datetime.now(timezone.utc).isoformat()
        atomic_json(output / 'state.json', state)

    def execute(stage, command):
        for name, checksum in sources.items():
            if digest_file(PROJECT / 'disruption' / name) != checksum:
                raise RuntimeError('Pinned workflow source changed: ' + name)
        if digest_file(engine) != config['engine_sha256']:
            raise RuntimeError('Pinned engine changed')
        resources(root)
        state.update(stage=stage, command=[str(item) for item in command])
        save()
        print(json.dumps({'stage': stage, 'output': str(output)}), flush=True)
        process = subprocess.Popen([str(item) for item in command], cwd=PROJECT, start_new_session=True)
        state['child_pid'] = process.pid
        save()
        try:
            while process.poll() is None:
                time.sleep(20)
                resources(root)
            if process.returncode:
                raise RuntimeError(f'{stage} exited {process.returncode}')
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            raise
        finally:
            state.pop('child_pid', None)

    try:
        save()
        while True:
            parent = json.loads((prerequisite / 'state.json').read_text())
            if parent['status'] == 'complete' and parent['stage'] == 'benchmark_complete':
                break
            if parent['status'] == 'interrupted':
                raise RuntimeError('Prerequisite interrupted: ' + str(parent.get('error')))
            live = subprocess.run(['systemctl', '--user', 'show', args.prerequisite_unit, '--property=SubState', '--value'],
                                  capture_output=True, text=True)
            if live.returncode == 0 and live.stdout.strip() not in ('running', 'start', 'start-pre'):
                raise RuntimeError('Prerequisite service is not live and completion is absent')
            state['prerequisite_stage'] = parent['stage']
            save()
            resources(root)
            time.sleep(30)
        graph_path = prerequisite / 'graph'
        graph = json.loads((graph_path / 'manifest.json').read_text())
        benchmark_path = prerequisite / 'benchmark-annual/manifest.json'
        benchmark = json.loads(benchmark_path.read_text())
        if (foundation_meta['status'] != 'complete' or graph['node_count'] != foundation_meta['rows']
                or graph['foundation_config_sha256'] != foundation_meta['config_sha256']
                or not benchmark['complete']
                or benchmark['graph_manifest_sha256'] != digest_file(graph_path / 'manifest.json')):
            raise RuntimeError('Prerequisite provenance or coverage mismatch')
        annual_path = output / 'annual'
        execute('all_annual', [engine, 'full', '--graph', graph_path, '--output', annual_path,
                              '--workers', args.workers, '--partition-size', args.partition_size,
                              '--batch-size', args.batch_size, '--verify-benchmark', benchmark_path])
        annual = json.loads((annual_path / 'manifest.json').read_text())
        if not annual['complete'] or annual['scope'] != 'all_graph_works':
            raise RuntimeError('Full annual job did not finish')
        analytical_path = output / 'analytical'
        execute('all_analytical', [sys.executable, '-m', 'disruption.src.bulk_results', annual_path / 'manifest.json',
                                  analytical_path, '--foundation', foundation, '--workers', args.export_workers])
        analytical = json.loads((analytical_path / 'manifest.json').read_text())
        expected = verify_coverage(graph, annual, analytical, foundation_meta)
        report = {'status': 'complete', 'scope': 'all_graph_works', 'works': expected, 'window_rows': expected * 8,
                  'annual_rows': analytical['annual_rows'], 'snapshot_date': graph['snapshot_date'],
                  'config': config, 'graph_manifest': str(graph_path / 'manifest.json'),
                  'graph_manifest_sha256': digest_file(graph_path / 'manifest.json'),
                  'annual_manifest': str(annual_path / 'manifest.json'),
                  'annual_manifest_sha256': digest_file(annual_path / 'manifest.json'),
                  'analytical_manifest': str(analytical_path / 'manifest.json'),
                  'analytical_manifest_sha256': digest_file(analytical_path / 'manifest.json'),
                  'quality_path': str(analytical_path / 'quality.json'),
                  'quality_sha256': digest_file(analytical_path / 'quality.json'),
                  'completed_at': datetime.now(timezone.utc).isoformat()}
        atomic_json(output / 'completion.json', report)
        state.update(status='complete', stage='all_statistics_cached', completion=str(output / 'completion.json'))
        save()
    except BaseException as error:
        state.update(status='interrupted', error=str(error))
        save()
        raise
    finally:
        lock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prerequisite', type=Path, required=True)
    parser.add_argument('--prerequisite-unit', default='disruption-advance-20260924.service')
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--artifact-root', type=Path, default=Path('/mnt/hg02/openalex-snapshot/analysis/disruption'))
    parser.add_argument('--workers', type=int, default=40, choices=range(1, 41))
    parser.add_argument('--export-workers', type=int, default=32, choices=range(1, 41))
    parser.add_argument('--partition-size', type=int, default=100000)
    parser.add_argument('--batch-size', type=int, default=1000)
    run(parser.parse_args())
