"""Convert verified foundation shards to compressed, loss-auditable Go input."""

import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import fcntl
import gzip
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import struct
import sys
import time

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from cache_foundation import atomic_json, digest_file, digest_json


NODE = struct.Struct('<QiIqq')
HEADER = struct.Struct('<Qq')
VERSION = 'graph-bridge-v1'


def guard(output, minimum_free, maximum_owned):
    if shutil.disk_usage(output).free < minimum_free:
        raise RuntimeError('Insufficient free disk space')
    owned = 0
    for path in output.rglob('*'):
        try:
            if path.is_file():
                owned += path.stat().st_size
        except FileNotFoundError:
            continue
    if owned > maximum_owned:
        raise RuntimeError('Owned output exceeds disk budget')


def convert_shard(task):
    source = Path(task['source'])
    destination = Path(task['destination'])
    saved = json.loads((source / 'complete.json').read_text())
    if saved.get('status') != 'complete' or saved.get('config_sha256') != task['foundation_config_sha256']:
        raise ValueError('Foundation checkpoint is incomplete or belongs to another configuration')
    if digest_file(source / 'complete.json') != task['checkpoint_sha256']:
        raise ValueError('Foundation checkpoint changed')
    for name, record in saved['outputs'].items():
        if digest_file(source / name) != record['sha256']:
            raise ValueError(f'Foundation checksum mismatch: {source / name}')
    destination.mkdir(parents=True, exist_ok=True)
    checkpoint = destination / 'complete.json'
    if checkpoint.exists():
        previous = json.loads(checkpoint.read_text())
        if previous['checkpoint_sha256'] != task['checkpoint_sha256'] or previous['config_sha256'] != task['config_sha256']:
            raise ValueError('Bridge input checkpoint changed')
        for name in ('nodes', 'references'):
            if digest_file(destination / (name + '.bin.gz')) != previous[name + '_sha256']:
                raise ValueError('Bridge output checksum mismatch')
        return previous
    pa.set_cpu_count(1)
    connection = duckdb.connect(config={'threads': 1, 'memory_limit': '2GiB'})
    connection.execute("SET temp_directory = ''")
    nodes_file = pq.ParquetFile(source / 'nodes.parquet')
    refs_file = pq.ParquetFile(source / 'raw_references.parquet')
    if nodes_file.metadata.num_rows != refs_file.metadata.num_rows:
        raise ValueError('Node/reference row count mismatch')
    if sys.byteorder != 'little':
        raise ValueError('Bridge Arrow buffers currently require little-endian host')
    rows = raw_entries = 0
    started = time.monotonic()
    try:
        with gzip.GzipFile(filename=str(destination / 'nodes.bin.gz.partial'), mode='wb', compresslevel=1, mtime=0) as nodes_out, gzip.GzipFile(filename=str(destination / 'references.bin.gz.partial'), mode='wb', compresslevel=1, mtime=0) as refs_out:
            nodes_batches = nodes_file.iter_batches(batch_size=16384, columns=['work_id_numeric', 'publication_year', 'openalex_cited_by_count', 'reference_count_raw'], use_threads=False)
            refs_batches = refs_file.iter_batches(batch_size=16384, use_threads=False)
            for nodes, references in zip(nodes_batches, refs_batches, strict=True):
                if shutil.disk_usage(destination).free < task['minimum_free']:
                    raise RuntimeError('Insufficient free disk space')
                connection.register('refs', pa.Table.from_batches([references]))
                numeric = connection.execute("""SELECT
                    CASE WHEN regexp_full_match(work_id, 'https://openalex[.]org/W[1-9][0-9]*')
                      THEN try_cast(substr(work_id, 23) AS UBIGINT) END AS source_id,
                    list_transform(referenced_works, reference ->
                      CASE WHEN regexp_full_match(reference, 'https://openalex[.]org/W[1-9][0-9]*')
                      THEN coalesce(try_cast(substr(reference, 23) AS UBIGINT), 0::UBIGINT)
                      ELSE 0::UBIGINT END) AS targets FROM refs""").fetch_arrow_table().combine_chunks()
                identifiers, years, cited, counts = [column.to_pylist() for column in nodes.columns]
                sources = numeric.column('source_id').to_pylist()
                if identifiers != sources or any(identifier is None or identifier == 0 for identifier in identifiers):
                    raise ValueError('Invalid or misaligned node IDs')
                targets = numeric.column('targets').chunk(0)
                offsets = targets.offsets.to_pylist()
                nulls = targets.is_null().to_pylist()
                values = targets.values
                payload = memoryview(values.buffers()[1]) if len(values) else memoryview(b'')
                node_buffer, ref_buffer = bytearray(), bytearray()
                for index, identifier in enumerate(identifiers):
                    year = years[index]
                    year = year if year is not None and 1 <= year <= 9999 else 0
                    count = -1 if counts[index] is None else counts[index]
                    actual = -1 if nulls[index] else offsets[index + 1] - offsets[index]
                    if count != actual:
                        raise ValueError('Reference list length changed')
                    node_buffer.extend(NODE.pack(identifier, year, 0, -1 if cited[index] is None else cited[index], count))
                    ref_buffer.extend(HEADER.pack(identifier, count))
                    if actual > 0:
                        start = (values.offset + offsets[index]) * 8
                        end = (values.offset + offsets[index + 1]) * 8
                        ref_buffer.extend(payload[start:end])
                        raw_entries += actual
                nodes_out.write(node_buffer)
                refs_out.write(ref_buffer)
                rows += len(identifiers)
        if rows != saved['rows']:
            raise ValueError('Bridge row count mismatch')
        if digest_file(source / 'complete.json') != task['checkpoint_sha256']:
            raise ValueError('Foundation checkpoint changed during conversion')
        result = {'checkpoint_sha256': task['checkpoint_sha256'], 'rows': rows,
                  'raw_reference_entries': raw_entries, 'seconds': time.monotonic() - started,
                  'source': saved['source'], 'config_sha256': task['config_sha256']}
        for name in ('nodes', 'references'):
            temporary = destination / (name + '.bin.gz.partial')
            with temporary.open('rb') as stream:
                os.fsync(stream.fileno())
            path = destination / (name + '.bin.gz')
            os.replace(temporary, path)
            result[name + '_sha256'] = digest_file(path)
            result[name + '_bytes'] = path.stat().st_size
        atomic_json(checkpoint, result)
        return result
    finally:
        connection.close()


def run(args):
    if not 1 <= args.workers <= 40:
        raise ValueError('workers must be 1..40')
    foundation = args.foundation.resolve()
    metadata = json.loads((foundation / 'run.json').read_text())
    inventory_hash = digest_file(foundation / 'input_inventory.json')
    if inventory_hash != metadata['input_inventory_sha256']:
        raise ValueError('Foundation input inventory changed')
    if metadata['status'] != 'complete' and not args.allow_partial_input:
        raise ValueError('Foundation not complete; partial graph construction is forbidden')
    checkpoints = sorted(foundation.glob('shards/*/complete.json'))
    if metadata['status'] == 'complete' and len(checkpoints) != metadata['expected_shards']:
        raise ValueError('Foundation completion coverage mismatch')
    if args.max_files is not None:
        if args.max_files < 1:
            raise ValueError('max-files must be positive')
        checkpoints = checkpoints[:args.max_files]
    config = {'schema_version': VERSION, 'foundation_config_sha256': metadata['config_sha256'],
              'foundation_inventory_sha256': inventory_hash,
              'code_sha256': digest_file(Path(__file__)), 'gzip_level': 1,
              'duckdb': duckdb.__version__, 'pyarrow': pa.__version__}
    config_hash = digest_json(config)
    output = args.output.resolve() / metadata['configuration']['snapshot_manifest_sha256'] / config_hash
    output.mkdir(parents=True, exist_ok=True)
    lock = (output / '.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    minimum = 0 if args.synthetic else 10**12
    if not args.synthetic and not output.is_relative_to(Path('/mnt/hg02')):
        raise ValueError('Production output must be on /mnt/hg02')
    guard(output, minimum, 4 * 10**12)
    tasks = [{'source': str(path.parent), 'destination': str(output / 'shards' / path.parent.name),
              'checkpoint_sha256': digest_file(path), 'config_sha256': config_hash, 'minimum_free': minimum,
              'foundation_config_sha256': metadata['config_sha256']}
             for path in checkpoints]
    records = []
    executor = ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context('spawn'))
    try:
        pending = {executor.submit(convert_shard, task): task for task in tasks}
        while pending:
            finished, _ = wait(pending, timeout=5, return_when=FIRST_COMPLETED)
            guard(output, minimum, 4 * 10**12)
            for future in finished:
                task = pending.pop(future)
                result = future.result()
                prefix = Path(task['destination']).relative_to(output)
                records.append({**result, 'nodes': str(prefix / 'nodes.bin.gz'),
                                'references': str(prefix / 'references.bin.gz')})
                print(json.dumps({'completed': len(records), 'selected': len(tasks)}), flush=True)
        current = json.loads((foundation / 'run.json').read_text())
        if (current['config_sha256'] != metadata['config_sha256']
                or current['configuration'] != metadata['configuration']
                or current['input_inventory_sha256'] != inventory_hash
                or digest_file(foundation / 'input_inventory.json') != inventory_hash):
            raise ValueError('Foundation identity changed during bridge conversion')
        complete = current['status'] == 'complete' and len(records) == current['expected_shards']
        document = {'schema_version': VERSION, 'status': 'complete' if complete else 'partial',
                    'snapshot_date': metadata['configuration']['snapshot_date'],
                    'foundation_config_sha256': metadata['config_sha256'],
                    'foundation_run': str(foundation), 'config': config, 'config_sha256': config_hash,
                    'rows': sum(record['rows'] for record in records), 'shards': sorted(records, key=lambda item: item['source'])}
        if complete and document['rows'] != current['rows']:
            raise ValueError('Foundation total row count mismatch')
        atomic_json(output / 'manifest.json', document)
        if args.result_file:
            args.result_file.parent.mkdir(parents=True, exist_ok=True)
            atomic_json(args.result_file, {'manifest': str(output / 'manifest.json'),
                                          'sha256': digest_file(output / 'manifest.json'),
                                          'status': document['status']})
        print(json.dumps({'manifest': str(output / 'manifest.json'), 'status': document['status']}), flush=True)
    except BaseException:
        for process in executor._processes.values():
            process.terminate()
        raise
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
        lock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--foundation', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('/mnt/hg02/openalex-snapshot/analysis/disruption/bridge'))
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--max-files', type=int)
    parser.add_argument('--result-file', type=Path)
    parser.add_argument('--allow-partial-input', action='store_true')
    parser.add_argument('--synthetic', action='store_true', help='Synthetic fixtures only, bypass production path/disk checks')
    run(parser.parse_args())
