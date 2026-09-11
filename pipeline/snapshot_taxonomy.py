"""Resumable article denominators and flagged counts for two-level taxonomies."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import threading
import time

import duckdb

from .validate_snapshot import atomic_json, digest, now


def run(release_dir, workers=6, threads=8, memory_limit='32GB'):
    release_dir = Path(release_dir)
    provenance = json.loads((release_dir/'provenance.json').read_text())
    validation_path = Path(provenance['validation_report'])
    validation = json.loads(validation_path.read_text())
    root = Path(validation['snapshot_dir'])
    if validation['status'] != 'validated' or validation['blockers'] or digest((root/'manifest.json').read_bytes()) != validation['manifest_sha256']:
        raise ValueError('Source validation failed')
    entries = [entry for entry in json.loads((validation_path.parent/'files.json').read_text()) if entry['entity'] == 'works']
    scan = json.loads((release_dir/'scan-complete.json').read_text())
    if scan['config_sha256'] != provenance['config_sha256'] or scan['files'] != len(entries):
        raise ValueError('Canonical scan mismatch')
    code_hash = digest(Path(__file__).read_bytes())
    config = {'version': 'taxonomy-cohorts-v1', 'code_sha256': code_hash, 'scan_config_sha256': provenance['config_sha256']}
    config_hash = digest(json.dumps(config, sort_keys=True).encode())
    output = release_dir/'taxonomy'/config_hash
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
        connection.execute(f'''CREATE OR REPLACE TEMP TABLE eligible AS
            SELECT source_work.id, source_work.is_retracted,
                CASE WHEN source_work.publication_year < 2000 THEN 0 ELSE source_work.publication_year END AS year,
                source_work.primary_topic.field.id AS field_id, source_work.primary_topic.subfield.id AS subfield_id,
                list_distinct(list_transform(list_filter(source_work.concepts, concept -> concept.level IN (0,1)
                    AND regexp_full_match(concept.id, 'https://openalex[.]org/C[1-9][0-9]*')),
                    concept -> struct_pack(id := concept.id, level := concept.level))) AS concepts
            FROM source_work LEFT JOIN identities USING(id)
            WHERE source_work.is_xpac IS FALSE AND source_work.type='article'
                AND source_work.publication_year BETWEEN 1 AND {int(cutoff[:4])}
                AND (source_work.publication_date IS NULL OR source_work.publication_date <= DATE '{cutoff}')
                AND coalesce(identities.document_role, CASE WHEN regexp_matches(coalesce(source_work.title, ''),
                    '(?i)^\\s*(retraction\\b|retracted\\b|withdrawal notice\\b|correction\\b|erratum\\b|corrigendum\\b|expression of concern\\b)')
                    THEN 'suspected_notice' ELSE 'unresolved' END) IN ('original_supported','unresolved')''')
        query = '''SELECT 'scope' AS dimension, 'all' AS group_id, year,
                count(*)::BIGINT AS denominator, count_if(is_retracted IS TRUE)::BIGINT AS flagged
            FROM eligible GROUP BY ALL
            UNION ALL SELECT 'field', coalesce(field_id, 'unknown'), year, count(*)::BIGINT, count_if(is_retracted IS TRUE)::BIGINT FROM eligible GROUP BY ALL
            UNION ALL SELECT 'subfield', coalesce(subfield_id, 'unknown'), year, count(*)::BIGINT, count_if(is_retracted IS TRUE)::BIGINT FROM eligible GROUP BY ALL
            UNION ALL SELECT 'concept' || CAST(concept.level AS VARCHAR), concept.id, year, count(*)::BIGINT, count_if(is_retracted IS TRUE)::BIGINT
                FROM (SELECT year, is_retracted, unnest(concepts) AS concept FROM eligible) GROUP BY ALL
            UNION ALL SELECT 'concept0', 'unknown', year, count(*)::BIGINT, count_if(is_retracted IS TRUE)::BIGINT
                FROM eligible WHERE coalesce(len(list_filter(concepts, concept -> concept.level=0)),0)=0 GROUP BY ALL
            UNION ALL SELECT 'concept1', 'unknown', year, count(*)::BIGINT, count_if(is_retracted IS TRUE)::BIGINT
                FROM eligible WHERE coalesce(len(list_filter(concepts, concept -> concept.level=1)),0)=0 GROUP BY ALL'''
        temporary = str(destination)+'.tmp'
        connection.execute("COPY ("+query+") TO '"+temporary.replace("'", "''")+"' (FORMAT PARQUET, COMPRESSION ZSTD)")
        os.replace(temporary, destination)
        atomic_json(marker, {'source_fingerprint': fingerprint, 'sha256': digest(destination.read_bytes())})
        connection.execute('DROP TABLE eligible')

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(process, entry) for entry in entries]
            for index, future in enumerate(as_completed(futures), 1):
                future.result()
                if index % 100 == 0:
                    print(f'Taxonomy cohorts: {index}/{len(entries)} shards; {time.monotonic()-started:.0f}s', flush=True)
    finally:
        for connection in connections:
            connection.close()
    if digest(Path(__file__).read_bytes()) != code_hash:
        raise ValueError('Taxonomy scanner changed during execution')
    marker = dict(config, config_sha256=config_hash, directory=str(output.resolve()), files=len(entries),
        elapsed_seconds=time.monotonic()-started, completed_at=now(),
        execution={'workers': workers, 'threads_per_worker': threads, 'memory_per_worker': memory_limit})
    atomic_json(release_dir/'taxonomy-complete.json', marker)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release_dir', type=Path)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--threads', type=int, default=8)
    parser.add_argument('--memory-limit', default='32GB')
    args = parser.parse_args()
    run(args.release_dir, args.workers, args.threads, args.memory_limit)
