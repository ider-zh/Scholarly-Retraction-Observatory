"""Read legacy Concepts for screened candidates without changing the Topic model."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import threading
import time

import duckdb

from .validate_snapshot import atomic_json, digest, now
from .work_policy import is_broad


def run(release_dir, workers=6, threads=8, memory_limit='24GB'):
    release_dir = Path(release_dir)
    provenance = json.loads((release_dir/'provenance.json').read_text())
    broad = is_broad(provenance)
    validation_path = Path(provenance['validation_report'])
    validation = json.loads(validation_path.read_text())
    root = Path(validation['snapshot_dir'])
    if validation['status'] != 'validated' or validation['blockers'] or digest((root/'manifest.json').read_bytes()) != validation['manifest_sha256']:
        raise ValueError('Source validation failed')
    entries = [entry for entry in json.loads((validation_path.parent/'files.json').read_text()) if entry['entity']=='works']
    scan = json.loads((release_dir/'scan-complete.json').read_text())
    if scan['config_sha256'] != provenance['config_sha256'] or scan['files'] != len(entries):
        raise ValueError('Canonical scan mismatch')
    code_hash = digest(Path(__file__).read_bytes())
    config = {'version': 'legacy-concepts-v1', 'code_sha256': code_hash, 'scan_config_sha256': provenance['config_sha256']}
    config_hash = digest(json.dumps(config, sort_keys=True).encode())
    output = release_dir/'concepts'/config_hash
    output.mkdir(parents=True, exist_ok=True)
    local, connections = threading.local(), []
    started = time.monotonic()
    cutoff = validation['oa_snapshot_date']

    def process(entry):
        source = root/entry['key']
        stat = source.stat()
        if stat.st_size != entry['actual_bytes'] or stat.st_mtime_ns != entry['mtime_ns']:
            raise ValueError('Source changed after validation')
        key = digest(entry['key'].encode())
        destination, marker = output/(key+'.parquet'), output/(key+'.json')
        fingerprint = digest(json.dumps(entry, sort_keys=True).encode())
        if marker.exists() and destination.exists():
            previous = json.loads(marker.read_text())
            if previous['source_fingerprint'] == fingerprint and previous['sha256'] == digest(destination.read_bytes()):
                return
        if not hasattr(local, 'connection'):
            local.connection = duckdb.connect(config={'threads': threads, 'memory_limit': memory_limit,
                'temp_directory': str(output/'spill'/str(threading.get_ident()))})
            connections.append(local.connection)
        connection = local.connection
        connection.read_parquet(str(source), hive_partitioning=False).create_view('source_work', replace=True)
        connection.read_parquet(str(release_dir/'shards'/key/'identifiers.parquet')).create_view('identities', replace=True)
        query = f'''SELECT source_work.id, source_work.concepts FROM source_work SEMI JOIN
            (SELECT id FROM identities WHERE is_xpac IS FALSE AND ({'TRUE' if broad else 'FALSE'} OR type='article')
                AND document_role IN ('original_supported','unresolved')
                AND publication_year BETWEEN 1 AND {int(cutoff[:4])}
                AND (publication_date IS NULL OR publication_date <= DATE '{cutoff}')) candidates USING(id)'''
        temporary = str(destination)+'.tmp'
        connection.execute("COPY ("+query+") TO '"+temporary.replace("'", "''")+"' (FORMAT PARQUET, COMPRESSION ZSTD)")
        os.replace(temporary, destination)
        atomic_json(marker, {'source_fingerprint': fingerprint, 'sha256': digest(destination.read_bytes())})

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(process, entry) for entry in entries]
            for index, future in enumerate(as_completed(futures), 1):
                future.result()
                if index % 100 == 0:
                    print(f'Concepts: {index}/{len(entries)} shards; {time.monotonic()-started:.0f}s', flush=True)
    finally:
        for connection in connections:
            connection.close()
    if digest(Path(__file__).read_bytes()) != code_hash:
        raise ValueError('Concept scanner changed during execution')
    atomic_json(release_dir/'concepts-complete.json', dict(config, config_sha256=config_hash, directory=str(output.resolve()),
        files=len(entries), elapsed_seconds=time.monotonic()-started, completed_at=now(),
        execution={'workers': workers, 'threads_per_worker': threads, 'memory_per_worker': memory_limit}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release_dir', type=Path)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--threads', type=int, default=8)
    parser.add_argument('--memory-limit', default='24GB')
    args = parser.parse_args()
    run(args.release_dir, args.workers, args.threads, args.memory_limit)
