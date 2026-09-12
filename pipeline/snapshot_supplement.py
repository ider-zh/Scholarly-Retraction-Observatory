"""Additional full-corpus denominators and fixed publication-followup cohorts."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import threading
import time

import duckdb
import pyarrow as pa

from .validate_snapshot import atomic_json, digest, now
from .work_policy import is_broad


def run(release_dir, workers=6, threads=8, memory_limit='32GB'):
    release_dir = Path(release_dir)
    provenance = json.loads((release_dir / 'provenance.json').read_text())
    broad = is_broad(provenance)
    validation_path = Path(provenance['validation_report'])
    validation = json.loads(validation_path.read_text())
    root = Path(validation['snapshot_dir'])
    if validation['status'] != 'validated' or validation['blockers'] or digest((root/'manifest.json').read_bytes()) != validation['manifest_sha256']:
        raise ValueError('Source validation failed')
    entries = [entry for entry in json.loads((validation_path.parent/'files.json').read_text()) if entry['entity']=='works']
    scan = json.loads((release_dir/'scan-complete.json').read_text())
    citations = json.loads((release_dir/'citations-complete.json').read_text())
    if scan['config_sha256'] != provenance['config_sha256'] or scan['files'] != len(entries) or citations['scan_config_sha256'] != provenance['config_sha256']:
        raise ValueError('Source/citation scan mismatch')
    targets = json.loads((Path(citations['directory'])/'targets.json').read_text())
    if digest(json.dumps(targets, sort_keys=True).encode()) != citations['targets_sha256']:
        raise ValueError('Target set changed')
    selected = pa.table({'id': pa.array([target['target_id'] for target in targets], type=pa.string()),
                         'event_date': pa.array([target['event_date'] for target in targets], type=pa.string())})
    code_hash = digest(Path(__file__).read_bytes())
    config = {'code_sha256': code_hash, 'scan_config_sha256': provenance['config_sha256'],
              'targets_sha256': citations['targets_sha256'], 'version': 'supplement-v1'}
    config_hash = digest(json.dumps(config, sort_keys=True).encode())
    output = release_dir/'supplement'/config_hash
    output.mkdir(parents=True, exist_ok=True)
    connections, local = [], threading.local()
    cutoff = validation['oa_snapshot_date']
    started = time.monotonic()

    def process(entry):
        source = root/entry['key']
        stat = source.stat()
        if stat.st_size != entry['actual_bytes'] or stat.st_mtime_ns != entry['mtime_ns']:
            raise ValueError('Source changed')
        key = digest(entry['key'].encode())
        fingerprint = digest(json.dumps(entry, sort_keys=True).encode())
        destination, marker = output/(key+'.parquet'), output/(key+'.json')
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
        connection.read_parquet(str(release_dir/'shards'/key/'identifiers.parquet')).create_view('roles', replace=True)
        connection.register('matched', selected)
        connection.execute(f'''CREATE OR REPLACE TEMP TABLE eligible AS
            SELECT source_work.id, source_work.type, source_work.publication_year, source_work.publication_date,
                source_work.is_retracted, CAST(matched.event_date AS DATE) AS event_date,
                coalesce(source_work.open_access.oa_status, 'Unknown') AS oa_status,
                coalesce(source_work.language, 'Unknown') AS language,
                CASE WHEN len(source_work.authorships) IS NULL OR len(source_work.authorships)=0 THEN 'Unknown'
                     WHEN len(source_work.authorships)=1 THEN '1'
                     WHEN len(source_work.authorships)<=5 THEN '2-5'
                     WHEN len(source_work.authorships)<=10 THEN '6-10'
                     WHEN len(source_work.authorships)<=50 THEN '11-50' ELSE '>50' END AS observed_team_band,
                CASE WHEN source_work.authors_count > len(source_work.authorships) THEN 'detected_truncation'
                     WHEN source_work.authors_count IS NULL OR source_work.authorships IS NULL THEN 'unknown'
                     WHEN source_work.authors_count < len(source_work.authorships) THEN 'count_conflict'
                     ELSE 'no_detected_truncation_not_proven_complete' END AS authorship_audit
            FROM source_work LEFT JOIN roles USING(id) LEFT JOIN matched USING(id)
            WHERE source_work.is_xpac IS FALSE AND ({'TRUE' if broad else 'FALSE'} OR source_work.type IN ('article','review'))
                AND source_work.publication_year BETWEEN 1 AND {int(cutoff[:4])}
                AND (source_work.publication_date IS NULL OR source_work.publication_date <= DATE '{cutoff}')
                AND coalesce(roles.document_role, CASE WHEN {'TRUE' if broad else 'FALSE'} THEN 'unresolved' WHEN regexp_matches(coalesce(source_work.title,''),
                    '(?i)^\\s*(retraction\\b|retracted\\b|withdrawal notice\\b|correction\\b|erratum\\b|corrigendum\\b|expression of concern\\b)')
                    THEN 'suspected_notice' ELSE 'unresolved' END) IN ('original_supported','unresolved')''')
        queries = []
        for dimension in ('oa_status', 'language', 'observed_team_band', 'authorship_audit'):
            queries.append(f'''SELECT '{dimension}' AS dimension, {dimension} AS group_id, type, publication_year,
                count(*)::BIGINT AS denominator, count(*) FILTER(WHERE is_retracted IS TRUE)::BIGINT AS flagged,
                count(*) FILTER(WHERE event_date <= DATE '{cutoff}')::BIGINT AS recorded
                FROM eligible GROUP BY ALL''')
        for years in (1, 3, 5):
            queries.append(f'''SELECT 'fixed_window' AS dimension, '{years}' AS group_id, type, publication_year,
                count(*)::BIGINT AS denominator, 0::BIGINT AS flagged,
                count(*) FILTER(WHERE event_date >= publication_date
                    AND event_date <= publication_date + INTERVAL '{years} years')::BIGINT AS recorded
                FROM eligible WHERE publication_date IS NOT NULL
                    AND publication_date + INTERVAL '{years} years' <= DATE '{cutoff}' GROUP BY ALL''')
        temporary = str(destination)+'.tmp'
        connection.execute("COPY ("+' UNION ALL '.join(queries)+") TO '"+temporary.replace("'", "''")+"' (FORMAT PARQUET, COMPRESSION ZSTD)")
        os.replace(temporary, destination)
        atomic_json(marker, {'source_fingerprint': fingerprint, 'sha256': digest(destination.read_bytes())})

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(process, entry) for entry in entries]
            for index, future in enumerate(as_completed(futures), 1):
                future.result()
                if index % 100 == 0:
                    print(f'Supplement: {index}/{len(entries)} shards; {time.monotonic()-started:.0f}s', flush=True)
    finally:
        for connection in connections:
            connection.close()
    if digest(Path(__file__).read_bytes()) != code_hash:
        raise ValueError('Supplement code changed during execution')
    atomic_json(release_dir/'supplement-complete.json', dict(config, config_sha256=config_hash, directory=str(output.resolve()),
        files=len(entries), completed_at=now(), elapsed_seconds=time.monotonic()-started,
        execution={'workers': workers, 'threads_per_worker': threads, 'memory_per_worker': memory_limit}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release_dir', type=Path)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--threads', type=int, default=8)
    parser.add_argument('--memory-limit', default='32GB')
    args = parser.parse_args()
    run(args.release_dir, args.workers, args.threads, args.memory_limit)
