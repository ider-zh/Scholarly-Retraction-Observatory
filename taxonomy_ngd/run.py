"""NGD benchmark and resumable production pipeline; never starts on import."""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import fcntl
import gzip
import json
import multiprocessing
import os
from pathlib import Path
import resource
import shutil
import subprocess
import time

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from taxonomy_ngd import core
from taxonomy_ngd.engine import COUNT_SCHEMA, connect, count_native, count_sql, decode_counts, encode_membership, literal, project


def code_identity():
    return {str(path): core.digest(path) for path in sorted(Path('taxonomy_ngd').glob('*'))
            if path.suffix in ('.py', '.go', '.rs')}


def guard():
    if shutil.disk_usage(core.ARTIFACTS).free < 10**12:
        raise RuntimeError('Disk reserve reached')
    if sum(path.stat().st_size for path in core.ARTIFACTS.rglob('*') if path.is_file()) > 4 * 10**12:
        raise RuntimeError('Artifact budget reached')


def bootstrap():
    core.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    prepared, entities = core.prepare()
    identity = core.identity({'input': prepared, 'code': code_identity(), 'version': core.VERSION})
    destination = core.ARTIFACTS / identity
    destination.mkdir(exist_ok=True)
    definition = {'identity': identity, 'input': prepared, 'code': code_identity(), 'version': core.VERSION}
    if (destination / 'definition.json.gz').exists():
        if core.read_json(destination / 'definition.json.gz') != definition:
            raise ValueError('Immutable run conflict')
    else:
        core.save_json(destination / 'definition.json.gz', definition)
        lookups = {name: {identifier: {key: row[key] for key in keys} for identifier, row in entities[name].items()}
                   for name, keys in [('concepts', ('id', 'level')), ('topics', ('id', 'subfield', 'field', 'domain'))]}
        core.save_json(destination / 'lookups.json.gz', lookups)
    return destination


def frozen(run):
    definition = core.read_json(run / 'definition.json.gz')
    if definition['code'] != code_identity():
        raise ValueError('Pipeline code changed; create new version')
    if core.digest(core.ROOT / 'manifest.json') != definition['input']['manifest_sha256']:
        raise ValueError('Source manifest changed')
    return definition


def worker(task):
    started = time.monotonic()
    cpu_started = time.process_time()
    child_started = resource.getrusage(resource.RUSAGE_CHILDREN)
    io_started = dict(line.split(': ') for line in Path('/proc/self/io').read_text().splitlines())
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    run = Path(task['run'])
    source = task['source']
    path = Path(source['path'])
    destination = Path(task['destination'])
    definition_hash = task['definition_hash']
    checkpoint = destination / 'complete.json.gz'
    if core.source_identity(path) != source['identity']:
        raise ValueError('Source file changed')
    if checkpoint.exists():
        saved = core.read_json(checkpoint)
        if saved['definition_hash'] != definition_hash or saved['source'] != source:
            raise ValueError('Checkpoint configuration mismatch')
        for name, metadata in saved['outputs'].items():
            if core.inspect_file(destination / name) != metadata:
                raise ValueError('Checkpoint output mismatch')
        return saved
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('membership', 'counts', 'audit'):
        (destination / (name + '.parquet.tmp')).unlink(missing_ok=True)
    entities = core.read_json(run / 'lookups.json.gz')
    connection = connect(entities)
    projection_start = time.monotonic()
    try:
        summary = project(connection, path)
        projection_seconds = time.monotonic() - projection_start
        if summary['rows'] != source['rows']:
            raise ValueError('Input row coverage mismatch')
        counting_start = time.monotonic()
        if task['engine'] == 'duckdb':
            counts = count_sql(connection)
        else:
            counts = count_native(connection, task['nodes'], task['binary'])
        count_seconds = time.monotonic() - counting_start
        table = pa.Table.from_pylist(counts, schema=COUNT_SCHEMA)
        core.parquet(destination / 'counts.parquet.tmp', table)
        for name, relation in [('membership', 'membership'), ('audit', 'audits')]:
            connection.execute(f"COPY {relation} TO {literal(destination / (name + '.parquet.tmp'))} (FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 3, ROW_GROUP_SIZE 65536)")
        if core.source_identity(path) != source['identity']:
            raise ValueError('Source changed during read')
        outputs = {}
        for name in ('membership', 'counts', 'audit'):
            temporary = destination / (name + '.parquet.tmp')
            with temporary.open('rb') as stream:
                os.fsync(stream.fileno())
            target = destination / (name + '.parquet')
            os.replace(temporary, target)
            outputs[target.name] = core.inspect_file(target)
        child_finished = resource.getrusage(resource.RUSAGE_CHILDREN)
        io_finished = dict(line.split(': ') for line in Path('/proc/self/io').read_text().splitlines())
        saved = {**summary, 'definition_hash': definition_hash, 'source': source, 'outputs': outputs,
                 'engine': task['engine'], 'wall_seconds': time.monotonic() - started,
                 'cpu_seconds': time.process_time() - cpu_started,
                 'child_cpu_seconds': child_finished.ru_utime + child_finished.ru_stime - child_started.ru_utime - child_started.ru_stime,
                 'io_delta': {key: int(io_finished[key])-int(io_started[key]) for key in io_started},
                 'projection_seconds': projection_seconds, 'count_seconds': count_seconds,
                 'process_peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
        core.save_json(checkpoint, saved)
        return saved
    finally:
        connection.close()


def benchmark(run):
    definition = frozen(run)
    directory = run / 'benchmark'
    directory.mkdir(exist_ok=True)
    binaries = {}
    for name, command in [('go', ['go', 'build', '-o', str(directory / 'count-go'), 'taxonomy_ngd/count.go']),
                          ('rust', ['rustc', '--edition=2021', '-O', 'taxonomy_ngd/count.rs', '-o', str(directory / 'count-rust')])]:
        subprocess.run(command, check=True)
        binaries[name] = str(directory / ('count-' + name))
    sources = [entry for entry in definition['input']['inventory'] if entry['entity'] == 'works' and entry['rows'] >= 100000]
    selected = [sources[0], sources[len(sources)//2], sources[-1]]
    results = []
    oracle_outputs = {}
    for index, source in enumerate(selected):
        for engine in ('duckdb', 'go', 'rust'):
            for repeat in range(3):
                destination = directory / f'sample-{index}-{engine}-{repeat}'
                task = {'run': str(run), 'source': source, 'destination': str(destination), 'definition_hash': core.identity(definition),
                        'engine': engine, 'binary': binaries.get(engine), 'nodes': definition['input']['nodes']}
                started = time.monotonic()
                context = multiprocessing.get_context('spawn')
                with ProcessPoolExecutor(max_workers=1, mp_context=context) as pool:
                    result = pool.submit(worker, task).result()
                elapsed = time.monotonic() - started
                semantic = sorted(pq.read_table(destination / 'counts.parquet').to_pylist(), key=lambda row: str(row))
                membership = pq.read_table(destination / 'membership.parquet').sort_by('work_id')
                audit = pq.read_table(destination / 'audit.parquet').sort_by([('row_index', 'ascending'), ('kind', 'ascending'), ('label_id', 'ascending')])
                if index not in oracle_outputs:
                    oracle_outputs[index] = (semantic, membership, audit)
                expected = oracle_outputs[index]
                if semantic != expected[0] or not membership.equals(expected[1]) or not audit.equals(expected[2]):
                    raise ValueError('Benchmark semantic disagreement')
                result.update(source_index=index, repeat=repeat, end_to_end_seconds=elapsed)
                results.append(result)
                print(json.dumps({'benchmark': engine, 'sample': index, 'repeat': repeat, 'seconds': elapsed}), flush=True)
    medians = {engine: sorted(sum(result['end_to_end_seconds'] for result in results if result['engine'] == engine and result['repeat'] == repeat)
                               for repeat in range(3))[1] for engine in ('duckdb', 'go', 'rust')}
    selected_engine = min(medians, key=medians.get)
    kernel = []
    for index in range(len(selected)):
        table = pq.read_table(directory / f'sample-{index}-duckdb-0/membership.parquet')
        encoded, dictionaries = encode_membership(table, definition['input']['nodes'])
        for engine, binary in binaries.items():
            for repeat in range(3):
                started = time.monotonic()
                output = subprocess.run([binary], input=encoded, capture_output=True, check=True).stdout
                elapsed = time.monotonic() - started
                decoded = sorted(decode_counts(output, dictionaries), key=lambda row: str(row))
                if decoded != oracle_outputs[index][0]:
                    raise ValueError('Kernel semantic disagreement')
                kernel.append({'source_index': index, 'engine': engine, 'repeat': repeat, 'seconds': elapsed, 'includes_process_and_pipe': True})
        for repeat in range(3):
            connection = duckdb.connect(config={'threads': '1', 'memory_limit': '6GiB'})
            connection.register('membership', table)
            started = time.monotonic()
            values = sorted(count_sql(connection), key=lambda row: str(row))
            kernel.append({'source_index': index, 'engine': 'duckdb', 'repeat': repeat, 'seconds': time.monotonic()-started})
            connection.close()
            if values != oracle_outputs[index][0]:
                raise ValueError('SQL kernel disagreement')
    scaling = []
    for workers in (1, 8, 16, 32, 40):
        tasks = [{'run': str(run), 'source': selected[index % len(selected)], 'destination': str(directory / f'scale-{workers}-{index}'),
                  'definition_hash': core.identity(definition), 'engine': selected_engine, 'binary': binaries.get(selected_engine),
                  'nodes': definition['input']['nodes']} for index in range(40)]
        started = time.monotonic()
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn')) as pool:
            values = list(pool.map(worker, tasks))
        elapsed = time.monotonic() - started
        scaling.append({'workers': workers, 'seconds': elapsed, 'rows': sum(value['rows'] for value in values),
                        'works_per_second': sum(value['rows'] for value in values)/elapsed,
                        'summed_process_cpu_seconds': sum(value['cpu_seconds'] for value in values),
                        'max_worker_peak_rss_kib': max(value['process_peak_rss_kib'] for value in values)})
        print(json.dumps({'scaling': scaling[-1]}), flush=True)
    chosen_workers = max(scaling, key=lambda result: result['works_per_second'])['workers']
    report = {'complete': True, 'definition_hash': core.identity(definition), 'results': results, 'kernel': kernel,
              'scaling': scaling, 'engine': selected_engine, 'workers': chosen_workers, 'medians': medians,
              'binaries': {name: {'path': path, 'sha256': core.digest(path)} for name, path in binaries.items()},
              'limitations': ['repeated-read cache state; not claimed cold', 'native routes share DuckDB projection; bridge cost included',
                              'scaling sweep single repetition per worker count; three repeats per candidate/sample',
                              'per-worker process peak is not concurrent cgroup peak'],
              'versions': {'go': subprocess.check_output(['go', 'version'], text=True).strip(),
                           'rust': subprocess.check_output(['rustc', '--version'], text=True).strip(),
                           'duckdb': duckdb.__version__, 'pyarrow': pa.__version__}}
    core.save_json(directory / 'report.json.gz', report)
    return report


def execute(run, workers=None):
    definition = frozen(run)
    benchmark_report = core.read_json(run / 'benchmark/report.json.gz')
    if not benchmark_report['complete'] or benchmark_report['definition_hash'] != core.identity(definition):
        raise ValueError('Benchmark gate not met')
    workers = workers or benchmark_report['workers']
    if not 1 <= workers <= 40:
        raise ValueError('Invalid workers')
    engine = benchmark_report['engine']
    binary = benchmark_report['binaries'].get(engine)
    if binary and core.digest(binary['path']) != binary['sha256']:
        raise ValueError('Native binary changed')
    sources = [entry for entry in definition['input']['inventory'] if entry['entity'] == 'works']
    guard()
    tasks = [{'run': str(run), 'source': source, 'destination': str(run / 'staging' / f'part-{index:06d}'),
              'definition_hash': core.identity(definition), 'engine': engine,
              'binary': binary['path'] if binary else None, 'nodes': definition['input']['nodes']}
             for index, source in enumerate(sources)]
    completed = []
    core.save_json(run / 'invocation.json.gz', {'workers': workers, 'engine': engine, 'started_at': datetime.now(timezone.utc).isoformat()})
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn')) as pool:
        for result in pool.map(worker, tasks, chunksize=1):
            completed.append(result)
            guard()
            core.save_json(run / 'progress.json.gz', {'status': 'running', 'parts': len(completed), 'expected_parts': len(tasks),
                                                     'rows': sum(part['rows'] for part in completed)})
            print(f'committed {len(completed)}/{len(tasks)} shards', flush=True)
    frozen(run)
    from taxonomy_ngd.publish import publish
    return publish(run, definition, completed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'benchmark', 'run'])
    parser.add_argument('--run', type=Path)
    parser.add_argument('--workers', type=int)
    args = parser.parse_args()
    if args.command == 'prepare':
        print(bootstrap())
        return
    run = args.run.resolve()
    with (run / '.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = benchmark(run) if args.command == 'benchmark' else execute(run, args.workers)
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
