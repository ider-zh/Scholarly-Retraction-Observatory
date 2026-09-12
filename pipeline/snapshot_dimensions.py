"""Extend a manifest-scoped scan with publication denominators by dimension."""

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
from .country_grouping import VERSION as COUNTRY_GROUPING, country_list_sql


VERSION = 'dimension-denominators-v2-country-grouping'


def run(release_dir, workers=4, threads=4, memory_limit='16GB'):
    release_dir = Path(release_dir)
    provenance = json.loads((release_dir / 'provenance.json').read_text())
    broad = is_broad(provenance)
    validation_path = Path(provenance['validation_report'])
    validation = json.loads(validation_path.read_text())
    source_root = Path(validation['snapshot_dir'])
    entries = [entry for entry in json.loads((validation_path.parent / 'files.json').read_text()) if entry['entity'] == 'works']
    local = threading.local()
    connections = []
    code_hash = digest(Path(__file__).read_bytes() + Path(__file__).with_name('country_grouping.py').read_bytes() + Path(__file__).with_name('work_policy.py').read_bytes() + provenance['config_sha256'].encode())
    output = release_dir / 'dimensions' / code_hash
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    def process(entry):
        key = digest(entry['key'].encode())
        shard = release_dir / 'shards' / key
        while not (shard / 'complete.json').exists():
            time.sleep(2)
        destination = output / (key + '.parquet')
        marker = output / (key + '.json')
        if marker.exists() and destination.exists():
            return
        source_path = source_root / entry['key']
        stat = source_path.stat()
        if stat.st_size != entry['actual_bytes'] or stat.st_mtime_ns != entry['mtime_ns']:
            raise ValueError('Source changed after validation: ' + entry['key'])
        if not hasattr(local, 'connection'):
            local.connection = duckdb.connect(config={'threads': threads, 'memory_limit': memory_limit,
                'temp_directory': str(output / 'spill' / str(threading.get_ident()))})
            connections.append(local.connection)
        connection = local.connection
        connection.read_parquet(str(source_path), hive_partitioning=False).create_view('source_work', replace=True)
        connection.read_parquet(str(shard / 'identifiers.parquet')).create_view('role_evidence', replace=True)
        connection.execute(f'''CREATE OR REPLACE TEMP TABLE eligible_dimensions AS
            WITH classified AS (
                SELECT source_work.*, coalesce(role_evidence.document_role, CASE
                    WHEN {'TRUE' if broad else 'FALSE'} THEN 'unresolved'
                    WHEN regexp_matches(coalesce(source_work.title, ''), '(?i)^\\s*(retraction\\b|retracted\\b|withdrawal notice\\b|correction\\b|erratum\\b|corrigendum\\b|expression of concern\\b)')
                    THEN 'suspected_notice' ELSE 'unresolved' END) AS role
                FROM source_work LEFT JOIN role_evidence USING (id)
                WHERE source_work.is_xpac IS FALSE AND ({'TRUE' if broad else 'FALSE'} OR source_work.type IN ('article', 'review'))
                    AND source_work.publication_year BETWEEN 1 AND {int(validation['oa_snapshot_date'][:4])}
                    AND (source_work.publication_date IS NULL OR source_work.publication_date <= DATE '{validation['oa_snapshot_date']}')
            ) SELECT id, type, publication_year, primary_topic.field.id AS field_id,
                primary_location.source.id AS source_id, primary_location.source.type AS source_type,
                list_distinct(list_filter(flatten(list_transform(authorships, author ->
                    list_transform(list_filter(author.institutions, institution ->
                        regexp_full_match(institution.id, 'https://openalex[.]org/I[1-9][0-9]*')
                        AND lower(trim(coalesce(institution.display_name, institution.id))) NOT IN ('unknown', 'unavailable', 'not available', 'unknown institution')),
                        institution -> institution.country_code))), country -> regexp_full_match(country, '[A-Z]{{2}}'))) AS institution_countries,
                list_distinct(list_filter(flatten(list_transform(authorships, author -> author.countries)),
                    country -> regexp_full_match(country, '[A-Z]{{2}}'))) AS authorship_countries
            FROM classified WHERE role IN ('original_supported', 'unresolved')''')
        connection.execute(f'''CREATE OR REPLACE TEMP TABLE eligible_dimensions AS
            SELECT * REPLACE (
                {country_list_sql('institution_countries')} AS institution_countries,
                {country_list_sql('authorship_countries')} AS authorship_countries
            ) FROM eligible_dimensions''')
        query = '''
            SELECT 'field' AS dimension, field_id AS group_id, type, publication_year,
                count(*)::BIGINT AS denominator, count(*)::DOUBLE AS weighted_denominator
            FROM eligible_dimensions GROUP BY ALL
            UNION ALL
            SELECT 'journal', source_id, type, publication_year, count(*)::BIGINT, count(*)::DOUBLE
            FROM eligible_dimensions WHERE source_type='journal' GROUP BY ALL
            UNION ALL
            SELECT 'institution_country', country, type, publication_year, count(*)::BIGINT, sum(weight)
            FROM (SELECT type, publication_year, unnest(institution_countries) AS country,
                         1.0/len(institution_countries) AS weight FROM eligible_dimensions) GROUP BY ALL
            UNION ALL
            SELECT 'authorship_country', country, type, publication_year, count(*)::BIGINT, sum(weight)
            FROM (SELECT type, publication_year, unnest(authorship_countries) AS country,
                         1.0/len(authorship_countries) AS weight FROM eligible_dimensions) GROUP BY ALL
        '''
        temporary = str(destination) + '.tmp'
        connection.execute(f"COPY ({query}) TO '{temporary.replace(chr(39), chr(39)*2)}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        os.replace(temporary, destination)
        atomic_json(marker, {'source_key': entry['key'], 'source_fingerprint': digest(json.dumps(entry, sort_keys=True).encode()), 'version': VERSION, 'country_grouping_version': COUNTRY_GROUPING})

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(process, entry) for entry in entries]
            for index, future in enumerate(as_completed(futures), 1):
                future.result()
                if index % 50 == 0:
                    print(f'Dimension denominators: {index}/{len(entries)} files; {time.monotonic()-started:.0f}s', flush=True)
    finally:
        for connection in connections:
            connection.close()
    atomic_json(release_dir / 'dimensions-complete.json', {'version': VERSION, 'code_sha256': code_hash, 'country_grouping_version': COUNTRY_GROUPING,
        'directory': str(output.resolve()), 'files': len(entries), 'completed_at': now(),
        'elapsed_seconds': time.monotonic()-started, 'execution': {'workers': workers, 'threads_per_worker': threads, 'memory_per_worker': memory_limit}})
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release_dir', type=Path)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--memory-limit', default='16GB')
    args = parser.parse_args()
    run(args.release_dir, args.workers, args.threads, args.memory_limit)
