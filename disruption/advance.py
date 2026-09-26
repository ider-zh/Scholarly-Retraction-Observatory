"""Guarded foundation -> full graph -> selected exact benchmark -> Parquet workflow."""

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'disruption/src'))
from cache_foundation import atomic_json, digest_file, digest_json


def resources(root):
    if shutil.disk_usage(root).free < 10**12:
        raise RuntimeError('At least 1 TB free space required')
    total = 0
    for path in root.rglob('*'):
        try:
            if path.is_file():
                total += path.stat().st_size
        except FileNotFoundError:
            continue
    if total > 4 * 10**12:
        raise RuntimeError('Disruption artifacts exceed owned 4 TB budget')


def run(args):
    foundation = args.foundation.resolve()
    output = args.output.resolve()
    if not output.is_relative_to(Path('/mnt/hg02')):
        raise ValueError('Production workflow output must be under /mnt/hg02')
    if not foundation.is_relative_to(output):
        raise ValueError('Foundation must be inside the common artifact root for aggregate disk accounting')
    output.mkdir(parents=True, exist_ok=True)
    foundation_metadata = json.loads((foundation / 'run.json').read_text())
    config = {'foundation_config_sha256': foundation_metadata['config_sha256'],
              'engine_sha256': digest_file(args.engine),
              'bridge_code_sha256': digest_file(PROJECT / 'disruption/src/graph_bridge.py'),
              'window_code_sha256': digest_file(PROJECT / 'disruption/src/window_results.py'),
              'orchestrator_sha256': digest_file(Path(__file__)),
              'benchmark_size_per_stratum': args.benchmark_size,
              'benchmark_workers': args.benchmark_workers, 'bridge_workers': args.bridge_workers}
    job = output / 'jobs' / digest_json(config)
    job.mkdir(parents=True, exist_ok=True)
    lock = (job / '.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = {'config': config, 'foundation': str(foundation), 'status': 'running', 'stage': 'await_foundation'}

    def save():
        state['updated_at'] = datetime.now(timezone.utc).isoformat()
        atomic_json(job / 'state.json', state)

    def execute(stage, command):
        resources(output)
        state.update(stage=stage, command=[str(item) for item in command])
        save()
        print(json.dumps({'stage': stage, 'job': str(job)}), flush=True)
        process = subprocess.Popen([str(item) for item in command], cwd=PROJECT, start_new_session=True)
        try:
            while process.poll() is None:
                time.sleep(10)
                resources(output)
            if process.returncode:
                raise RuntimeError(f'{stage} failed with exit {process.returncode}')
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            raise

    try:
        save()
        while True:
            metadata = json.loads((foundation / 'run.json').read_text())
            if metadata['config_sha256'] != config['foundation_config_sha256']:
                raise RuntimeError('Foundation configuration changed')
            if metadata['status'] == 'complete':
                break
            if metadata['status'] not in ('running', 'pilot_complete'):
                raise RuntimeError('Foundation interrupted; resume it before advancing')
            state['foundation_status'] = metadata['status']
            save()
            resources(output)
            time.sleep(30)
        for source, key in [('graph_bridge.py', 'bridge_code_sha256'), ('window_results.py', 'window_code_sha256')]:
            if digest_file(PROJECT / 'disruption/src' / source) != config[key]:
                raise RuntimeError('Scheduled code changed; launch a new immutable job')
        if digest_file(args.engine) != config['engine_sha256']:
            raise RuntimeError('Scheduled engine binary changed')
        bridge_pointer = job / 'bridge.json'
        execute('bridge', [sys.executable, PROJECT / 'disruption/src/graph_bridge.py', '--foundation', foundation,
                          '--output', output / 'bridge', '--workers', args.bridge_workers, '--result-file', bridge_pointer])
        pointer = json.loads(bridge_pointer.read_text())
        if pointer['status'] != 'complete' or digest_file(pointer['manifest']) != pointer['sha256']:
            raise RuntimeError('Bridge is incomplete or changed')
        graph = job / 'graph'
        if not (graph / 'manifest.json').exists():
            execute('graph', [args.engine, 'build', '--input', pointer['manifest'], '--output', graph])
        graph_metadata = json.loads((graph / 'manifest.json').read_text())
        if (graph_metadata['status'] != 'complete'
                or graph_metadata['bridge_manifest_sha256'] != pointer['sha256']
                or graph_metadata['foundation_config_sha256'] != config['foundation_config_sha256']):
            raise RuntimeError('Graph provenance does not match this workflow')
        counts = job / 'benchmark-annual'
        execute('benchmark', [args.engine, 'count', '--graph', graph, '--output', counts,
                             '--benchmark-size', args.benchmark_size, '--workers', args.benchmark_workers,
                             '--partition-size', 1000])
        manifest = json.loads((counts / 'manifest.json').read_text())
        if not manifest['complete']:
            raise RuntimeError('Benchmark incomplete')
        for index in range(len(manifest['partitions'])):
            destination = job / 'analytical' / f'partition-{index:08d}'
            if destination.exists():
                previous = json.loads((destination / 'manifest.json').read_text())
                if (previous['status'] != 'complete'
                        or previous['config']['input_manifest_sha256'] != digest_file(counts / 'manifest.json')
                        or previous['config']['code_sha256'] != config['window_code_sha256']
                        or previous['config']['partition_index'] != index):
                    raise RuntimeError('Existing analytical output has incompatible provenance')
                for item in previous['outputs'].values():
                    if digest_file(destination / item['path']) != item['sha256']:
                        raise RuntimeError('Existing analytical output checksum mismatch')
                continue
            execute('windows', [sys.executable, PROJECT / 'disruption/src/window_results.py', counts / 'manifest.json',
                               destination, '--partition-index', index, '--compression-level', 1])
        state.update(status='complete', stage='benchmark_complete',
                     scope='selected_focals_full_graph_neighborhood', full_annual_statistics='not_started',
                     graph=str(graph), annual=str(counts), analytical=str(job / 'analytical'))
        save()
    except BaseException as error:
        state.update(status='interrupted', error=str(error))
        save()
        raise
    finally:
        lock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--foundation', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=Path('/mnt/hg02/openalex-snapshot/analysis/disruption'))
    parser.add_argument('--engine', required=True, type=Path)
    parser.add_argument('--bridge-workers', type=int, default=16, choices=range(1, 41))
    parser.add_argument('--benchmark-workers', type=int, default=4, choices=range(1, 41))
    parser.add_argument('--benchmark-size', type=int, default=8)
    run(parser.parse_args())
