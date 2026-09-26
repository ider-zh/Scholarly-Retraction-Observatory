"""Bounded real-column codec benchmark; never a graph coverage claim."""

import argparse
import hashlib
import json
from pathlib import Path
import time

import pyarrow as pa
import pyarrow.parquet as pq


def run(snapshot, output, rows):
    manifest_path = snapshot / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entries = next(entity['files'] for entity in manifest['entities'] if entity['entity'] == 'works')
    ordered = sorted(entries, key=lambda entry: entry['meta']['content_length'])
    selected = [ordered[len(ordered) // 2], ordered[-1]]
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for index, entry in enumerate(selected):
        source = snapshot / entry['url'].split('/parquet/', 1)[1]
        parquet = pq.ParquetFile(source)
        columns = ['id', 'publication_year', 'type', 'is_xpac', 'referenced_works', 'primary_topic']
        batch = next(parquet.iter_batches(batch_size=rows, columns=columns))
        table = pa.Table.from_batches([batch]).replace_schema_metadata(None)
        for codec, level in [('NONE', None), ('snappy', None), ('zstd', 1), ('zstd', 3), ('zstd', 6)]:
            destination = output / f'sample-{index}-{codec}-{level}.parquet'
            settings = {} if level is None else {'compression_level': level}
            started = time.perf_counter()
            pq.write_table(table, destination, compression=codec, **settings)
            write_seconds = time.perf_counter() - started
            started = time.perf_counter()
            restored = pq.ParquetFile(destination).read()
            read_seconds = time.perf_counter() - started
            if not table.equals(restored):
                raise ValueError('Codec roundtrip changed data')
            results.append({'source': str(source), 'rows': table.num_rows,
                            'arrow_bytes': table.nbytes, 'codec': codec, 'level': level,
                            'file_bytes': destination.stat().st_size,
                            'write_seconds': write_seconds, 'warm_read_seconds': read_seconds})
    report = {'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
              'pyarrow': pa.__version__, 'results': results,
              'limitations': 'Two shard prefixes, not random Works; warm page cache, single repeat; no fsync throughput guarantee.'}
    (output / 'compression.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rows', type=int, default=100000)
    arguments = parser.parse_args()
    run(arguments.snapshot, arguments.output, arguments.rows)
