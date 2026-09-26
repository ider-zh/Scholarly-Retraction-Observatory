"""Read manifest and Parquet footers, not citation payloads, for capacity planning."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq


def run(snapshot, output):
    manifest_path = snapshot / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entity = next(item for item in manifest['entities'] if item['entity'] == 'works')

    def inspect(entry):
        path = snapshot / entry['url'].split('/parquet/', 1)[1]
        metadata = pq.ParquetFile(path).metadata
        if path.stat().st_size != entry['meta']['content_length'] or metadata.num_rows != entry['meta']['record_count']:
            raise ValueError(f'Manifest mismatch: {path}')
        slots = 0
        compressed = 0
        for group_index in range(metadata.num_row_groups):
            group = metadata.row_group(group_index)
            for column_index in range(group.num_columns):
                column = group.column(column_index)
                if column.path_in_schema.startswith('referenced_works.'):
                    slots += column.num_values
                    compressed += column.total_compressed_size
        return {'rows': metadata.num_rows, 'reference_leaf_slots': slots,
                'reference_column_compressed_bytes': compressed}

    with ThreadPoolExecutor(max_workers=16) as executor:
        shards = list(executor.map(inspect, entity['files']))
    totals = {key: sum(item[key] for item in shards) for key in shards[0]}
    nodes = totals['rows']
    slots = totals['reference_leaf_slots']
    report = {'snapshot_date': manifest['date'], 'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
              'files': len(shards), **totals,
              'csr_two_directions_uint32_estimate_bytes': slots * 8 + (nodes + 1) * 16,
              'dense_uint32_scratch_per_worker_bytes': nodes * 4,
              'limitations': 'Leaf slots include null/empty list placeholders and duplicates; not canonical edge count. CSR estimate excludes ID map, years, build buffers, allocator and per-worker scratch. No closure audit performed.'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    run(arguments.snapshot, arguments.output)
