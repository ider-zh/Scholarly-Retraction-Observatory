"""Summarize committed foundation shards without reading graph payloads."""

import argparse
import json
from pathlib import Path


def summarize(root):
    for run_path in sorted(root.glob('*/*/run.json')):
        run = json.loads(run_path.read_text())
        shards = [json.loads(path.read_text()) for path in run_path.parent.glob('shards/*/complete.json')]
        outputs = sum(item['bytes'] for shard in shards for item in shard['outputs'].values())
        print(json.dumps({'run_root': str(run_path.parent), 'status': run['status'],
                          'committed_shards': len(shards), 'expected_shards': run['expected_shards'],
                          'committed_rows': sum(shard['rows'] for shard in shards),
                          'raw_reference_entries': sum(shard['raw_reference_entries'] for shard in shards),
                          'compressed_output_bytes': outputs,
                          'network_statistics': run['network_statistics'],
                          'note': 'Checkpoint summary, not a fresh output checksum verification; inspect service for liveness.'},
                         ensure_ascii=False))
    for path in sorted((root.parent / 'jobs').glob('*/state.json')):
        job = json.loads(path.read_text())
        print(json.dumps({'job': str(path.parent), 'status': job['status'], 'stage': job['stage'],
                          'updated_at': job['updated_at'], 'error': job.get('error'),
                          'scope': job.get('scope'),
                          'full_annual_statistics': job.get('full_annual_statistics', 'not_started')},
                         ensure_ascii=False))
    for path in sorted((root.parent / 'full-runs').glob('*/state.json')):
        job = json.loads(path.read_text())
        analytical_stage = job['stage'] in ('all_analytical', 'all_statistics_cached')
        progress_path = path.parent / ('analytical/progress.json' if analytical_stage else 'annual/progress.json')
        progress = json.loads(progress_path.read_text()) if progress_path.exists() else None
        print(json.dumps({'full_run': str(path.parent), 'status': job['status'], 'stage': job['stage'],
                          'updated_at': job['updated_at'], 'error': job.get('error'),
                          'prerequisite_stage': job.get('prerequisite_stage'), 'progress': progress,
                          'completion': job.get('completion')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/mnt/hg02/openalex-snapshot/analysis/disruption/foundation'))
    summarize(parser.parse_args().root)
