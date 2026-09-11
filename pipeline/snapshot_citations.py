"""Manifest-scoped incoming edges, with immutable target and shard checkpoints."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import threading
import time

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from .validate_snapshot import atomic_json, digest, now


VERSION = 'incoming-edges-v1'


def prepare_targets(release_dir, entries, cutoff):
    matches = json.loads((release_dir / 'rw_oa_match.json').read_text())
    papers = json.loads((release_dir / 'rw_original.json').read_text())
    linked = {}
    for paper in papers:
        match = matches[paper['id']]
        if match['match_outcome'] == 'unique' and match['selected_id']:
            linked.setdefault(match['selected_id'], []).append(paper)
    targets = []
    for entry in entries:
        shard = release_dir / 'shards' / digest(entry['key'].encode())
        for work in pq.ParquetFile(shard / 'identifiers.parquet').read().to_pylist():
            if work['id'] not in linked or work['is_xpac'] is not False or work['type'] != 'article':
                continue
            if work['document_role'] not in {'original_supported', 'unresolved'}:
                continue
            if not work['publication_year'] or not 1 <= work['publication_year'] <= int(cutoff[:4]):
                continue
            if work['publication_date'] and str(work['publication_date']) > cutoff:
                continue
            originals = linked[work['id']]
            events = {paper['retracted'] for paper in originals if paper['retracted']}
            event = next(iter(events)) if len(events) == 1 and all(paper['retracted'] for paper in originals) else None
            targets.append({'target_id': work['id'], 'publication_date': str(work['publication_date']) if work['publication_date'] else None,
                'publication_year': work['publication_year'], 'event_date': event,
                'event_date_conflict': len(events) > 1, 'event_after_cutoff': bool(event and event > cutoff),
                'precision': 'day_reported_original_precision_unknown'})
    return sorted(targets, key=lambda row: row['target_id'])


def scan_file(connection, source, targets, destination):
    connection.read_parquet(str(source), hive_partitioning=False).create_view('source_work', replace=True)
    connection.register('citation_targets', targets)
    connection.execute('''CREATE OR REPLACE TEMP TABLE incoming AS
        SELECT DISTINCT citing_id, target_id, publication_date, publication_year, type, is_xpac
        FROM (SELECT id AS citing_id, unnest(referenced_works) AS target_id,
                     publication_date, publication_year, type, is_xpac FROM source_work)
        INNER JOIN citation_targets USING (target_id)''')
    count = connection.execute('SELECT count(*) FROM incoming').fetchone()[0]
    temporary = str(destination) + '.tmp'
    connection.execute("COPY incoming TO '" + temporary.replace("'", "''") + "' (FORMAT PARQUET, COMPRESSION ZSTD)")
    os.replace(temporary, destination)
    return count


def run(release_dir, workers=6, threads=8, memory_limit='32GB'):
    release_dir = Path(release_dir)
    provenance = json.loads((release_dir / 'provenance.json').read_text())
    validation_path = Path(provenance['validation_report'])
    validation = json.loads(validation_path.read_text())
    if validation['status'] != 'validated' or validation['blockers']:
        raise ValueError('Source gate must pass')
    root = Path(validation['snapshot_dir'])
    if digest((root / 'manifest.json').read_bytes()) != validation['manifest_sha256']:
        raise ValueError('Source manifest changed')
    entries = [entry for entry in json.loads((validation_path.parent / 'files.json').read_text()) if entry['entity'] == 'works']
    scan = json.loads((release_dir / 'scan-complete.json').read_text())
    if scan['files'] != len(entries) or scan['config_sha256'] != provenance['config_sha256']:
        raise ValueError('Incomplete canonical scan')
    targets = prepare_targets(release_dir, entries, validation['oa_snapshot_date'])
    target_hash = digest(json.dumps(targets, sort_keys=True).encode())
    code_hash = digest(Path(__file__).read_bytes())
    config = {'version': VERSION, 'scan_config_sha256': provenance['config_sha256'],
              'code_sha256': code_hash, 'targets_sha256': target_hash,
              'oa_manifest_sha256': validation['manifest_sha256'], 'citing_corpus': 'all'}
    config_hash = digest(json.dumps(config, sort_keys=True).encode())
    output = release_dir / 'citations' / config_hash
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / 'targets.json', targets)
    target_table = pa.table({'target_id': pa.array([row['target_id'] for row in targets], type=pa.string())})
    started = time.monotonic()
    local, connections = threading.local(), []

    def process(entry):
        key = digest(entry['key'].encode())
        path = root / entry['key']
        stat = path.stat()
        if stat.st_size != entry['actual_bytes'] or stat.st_mtime_ns != entry['mtime_ns']:
            raise ValueError('Source changed: ' + entry['key'])
        fingerprint = digest(json.dumps(entry, sort_keys=True).encode())
        marker, destination = output / (key + '.json'), output / (key + '.parquet')
        if marker.exists() and destination.exists():
            previous = json.loads(marker.read_text())
            if previous['source_fingerprint'] == fingerprint and previous['config_sha256'] == config_hash:
                if digest(destination.read_bytes()) == previous['output_sha256']:
                    return previous['edges']
        if not hasattr(local, 'connection'):
            local.connection = duckdb.connect(config={'threads': threads, 'memory_limit': memory_limit,
                'temp_directory': str(output / 'spill' / str(threading.get_ident()))})
            connections.append(local.connection)
        count = scan_file(local.connection, path, target_table, destination)
        atomic_json(marker, {'source_key': entry['key'], 'source_fingerprint': fingerprint,
            'config_sha256': config_hash, 'edges': count, 'output_sha256': digest(destination.read_bytes())})
        return count

    total = 0
    print(f'Incoming scan: {len(targets)} targets; {workers} workers × {threads} threads; {output}', flush=True)
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(process, entry) for entry in entries]
            for index, future in enumerate(as_completed(futures), 1):
                total += future.result()
                if index % 25 == 0:
                    print(f'Incoming edges: {index}/{len(entries)} shards; {total:,} edges; {time.monotonic()-started:.0f}s', flush=True)
    finally:
        for connection in connections:
            connection.close()
    if digest(Path(__file__).read_bytes()) != code_hash:
        raise ValueError('Scanner code changed during execution')
    marker = dict(config, config_sha256=config_hash, directory=str(output.resolve()), files=len(entries),
        targets=len(targets), edges=total, completed_at=now(), elapsed_seconds=time.monotonic()-started,
        execution={'workers': workers, 'threads_per_worker': threads, 'memory_per_worker': memory_limit})
    atomic_json(release_dir / 'citations-complete.json', marker)
    return marker


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release_dir', type=Path)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--threads', type=int, default=8)
    parser.add_argument('--memory-limit', default='32GB')
    args = parser.parse_args()
    run(args.release_dir, args.workers, args.threads, args.memory_limit)
