"""Offline manifest-scoped OpenAlex/RW analysis; full records remain local."""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import datetime as dt
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import threading
from urllib.parse import unquote

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from .build import date, doi, parts
from .validate_snapshot import atomic_json, digest, now


METHODS = 'snapshot-analysis-v1'
ROLE_POLICY = 'rw-identifiers-notice-types-title-sensitivity-v1'


def pmid(value):
    value = re.sub(r'^https?://(?:www[.])?(?:pubmed[.]ncbi[.]nlm[.]nih[.]gov/|ncbi[.]nlm[.]nih[.]gov/pubmed/)', '', (value or '').strip()).strip('/')
    return str(int(value)) if value.isdigit() and int(value) > 0 else None


def canonicalize_rw(csv_path, snapshot_date):
    papers, notices, role_ids = {}, {}, set()
    accounting = Counter()
    with open(csv_path, encoding='utf-8-sig', newline='') as source:
        for row in csv.DictReader(source):
            accounting['source_rows'] += 1
            original_doi, original_pmid = doi(row.get('OriginalPaperDOI')), pmid(row.get('OriginalPaperPubMedID'))
            notice_doi, notice_pmid = doi(row.get('RetractionDOI')), pmid(row.get('RetractionPubMedID'))
            for namespace, identifier, role in (
                ('doi', original_doi, 'original'), ('pmid', original_pmid, 'original'),
                ('doi', notice_doi, 'notice'), ('pmid', notice_pmid, 'notice'),
            ):
                if identifier:
                    role_ids.add((namespace, identifier, role))
            record_id = row['Record ID']
            original_key = 'doi:' + original_doi if original_doi else 'pmid:' + original_pmid if original_pmid else 'rw:' + record_id
            nature = row.get('RetractionNature', '').strip()
            event_date, publication_date = date(row.get('RetractionDate')), date(row.get('OriginalPaperDate'))
            notice_key = (notice_doi or notice_pmid or 'rw:' + record_id, nature, event_date)
            notice = notices.setdefault(notice_key, {'doi': notice_doi, 'pmid': notice_pmid,
                'nature': nature, 'date': event_date, 'record_ids': set(), 'original_ids': set(), 'reasons': set()})
            notice['record_ids'].add(record_id)
            notice['original_ids'].add(original_key)
            notice['reasons'].update(parts(row.get('Reason')))
            if nature.lower() != 'retraction':
                accounting['excluded_' + (nature.lower() or 'unknown')] += 1
                continue
            if event_date and event_date > snapshot_date:
                accounting['future_retraction_rows'] += 1
                continue
            accounting['included_retraction_rows'] += 1
            paper = papers.setdefault(original_key, {'id': original_key, 'doi': original_doi,
                'pmids': set(), 'rw_ids': set(), 'publication_dates': set(), 'event_dates': set(),
                'reasons': set(), 'subjects': set(), 'rw_countries': set(), 'raw_dates': [], 'title': row.get('Title', '')})
            if original_pmid:
                paper['pmids'].add(original_pmid)
            paper['rw_ids'].add(record_id)
            if publication_date:
                paper['publication_dates'].add(publication_date)
            if event_date:
                paper['event_dates'].add(event_date)
            paper['reasons'].update(parts(row.get('Reason')))
            paper['subjects'].update(parts(row.get('Subject')))
            paper['rw_countries'].update(parts(row.get('Country')))
            paper['raw_dates'].append({'record_id': record_id, 'publication': row.get('OriginalPaperDate'), 'event': row.get('RetractionDate')})
    for paper in papers.values():
        for key, value in list(paper.items()):
            if isinstance(value, set):
                paper[key] = sorted(value)
        paper['published'] = min(paper['publication_dates'], default=None)
        paper['retracted'] = min(paper['event_dates'], default=None)
        paper['publication_date_conflict'] = len(paper['publication_dates']) > 1
        paper['date_precision'] = 'day_reported_original_precision_unknown'
        paper['lag_days'] = ((dt.date.fromisoformat(paper['retracted']) - dt.date.fromisoformat(paper['published'])).days
                             if paper['published'] and paper['retracted'] else None)
        paper['negative_lag'] = paper['lag_days'] is not None and paper['lag_days'] < 0
        if paper['negative_lag']:
            paper['lag_days'] = None
    for notice in notices.values():
        for key, value in list(notice.items()):
            if isinstance(value, set):
                notice[key] = sorted(value)
    accounting['originals'] = len(papers)
    accounting['notice_records_all_categories'] = len(notices)
    accounting['duplicate_original_rows'] = accounting['included_retraction_rows'] - len(papers)
    return list(papers.values()), list(notices.values()), sorted(role_ids), dict(accounting)


def select_match(paper, by_doi, by_pmid):
    doi_candidates = set(by_doi.get(paper['doi'], ())) if paper['doi'] else set()
    pmid_sets = [set(by_pmid.get(identifier, ())) for identifier in paper['pmids']]
    pmid_candidates = set().union(*pmid_sets) if pmid_sets else set()
    candidates = doi_candidates | pmid_candidates
    conflicting = (len(paper['pmids']) > 1 or
                   bool(doi_candidates and pmid_candidates and doi_candidates != pmid_candidates))
    if conflicting:
        outcome = 'conflicting'
    elif len(candidates) > 1:
        outcome = 'ambiguous'
    elif len(candidates) == 1:
        outcome = 'unique'
    else:
        outcome = 'unmatched'
    return {'match_method': 'exact_doi' if doi_candidates else 'exact_pmid' if pmid_candidates else 'none',
            'match_outcome': outcome, 'selected_id': next(iter(candidates)) if outcome == 'unique' else None,
            'candidate_ids': sorted(candidates), 'oa_record_state': 'present' if candidates else 'absent'}


def country_sets(work):
    institutions, authorship_countries, author_ids, institution_ids = {}, set(), set(), {}
    authorships = work.get('authorships') or []
    missing_authorship_countries = 0
    for authorship in authorships:
        identifier = (authorship.get('author') or {}).get('id')
        if identifier and re.fullmatch(r'https://openalex.org/A[1-9][0-9]*', identifier) and not identifier.endswith('/A9999999999'):
            author_ids.add(identifier)
        countries = {value for value in authorship.get('countries') or [] if re.fullmatch('[A-Z]{2}', value or '')}
        authorship_countries.update(countries)
        if not countries:
            missing_authorship_countries += 1
        for institution in authorship.get('institutions') or []:
            identifier = institution.get('id')
            if not identifier or not re.fullmatch(r'https://openalex.org/I[1-9][0-9]*', identifier):
                continue
            label = institution.get('display_name') or identifier
            if label.strip().lower() in {'unknown', 'unavailable', 'not available', 'unknown institution'}:
                continue
            institution_ids[identifier] = label
            country = institution.get('country_code')
            if country and re.fullmatch('[A-Z]{2}', country):
                institutions[country] = True
    author_count = work.get('authors_count')
    incomplete = missing_authorship_countries > 0 or (author_count is not None and author_count > len(authorships))
    modes = {}
    for mode, countries in [('institution_country', set(institutions)), ('authorship_country', authorship_countries)]:
        if len(countries) >= 2:
            collaboration = 'multi_country_observed'
        elif not countries:
            collaboration = 'country_unknown'
        elif incomplete or (mode == 'institution_country' and any(not entry.get('institutions') for entry in authorships)):
            collaboration = 'single_country_incomplete'
        else:
            collaboration = 'completeness_unknown'
        modes[mode] = {'countries': sorted(countries), 'collaboration': collaboration}
    return modes, sorted(author_ids), institution_ids


def quantile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower, upper = math.floor(index), math.ceil(index)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def cohort_rate(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator,
            'value': 10000 * numerator / denominator if denominator else None,
            'ranking_eligible': denominator >= 1000 and numerator >= 20,
            'status': 'ready' if denominator else 'missing_denominator'}


def scan_snapshot(validation_path, rw_csv, rw_source, output, memory_limit='32GB', threads=6, workers=8):
    validation_path, output = Path(validation_path), Path(output).resolve()
    repository = Path(__file__).resolve().parents[1]
    if output.is_relative_to(repository) and not output.is_relative_to(repository / 'data/processed'):
        raise ValueError('Analytical records must be outside the repository or in ignored data/processed')
    validation = json.loads(validation_path.read_text())
    if validation['status'] != 'validated' or validation['blockers']:
        raise ValueError('Source validation must pass before analysis')
    root = Path(validation['snapshot_dir'])
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError('Analytical output must be separate from source files')
    if digest((root / 'manifest.json').read_bytes()) != validation['manifest_sha256']:
        raise ValueError('Snapshot manifest changed after validation')
    rw_meta = json.loads(Path(rw_source).read_text())
    if digest(Path(rw_csv).read_bytes()) != rw_meta['rw_csv_sha256']:
        raise ValueError('RW source hash mismatch')
    config = {'methods': METHODS, 'role_policy': ROLE_POLICY,
              'pipeline_sha256': digest(Path(__file__).read_bytes()),
              'oa_manifest_sha256': validation['manifest_sha256'],
              'rw_csv_sha256': rw_meta['rw_csv_sha256']}
    config_hash = digest(json.dumps(config, sort_keys=True).encode())
    release = output / config_hash
    release.mkdir(parents=True, exist_ok=True)
    papers, notices, role_ids, rw_accounting = canonicalize_rw(rw_csv, rw_meta['rw_snapshot_date'])
    atomic_json(release / 'rw_original.json', papers)
    atomic_json(release / 'rw_notice.json', notices)
    atomic_json(release / 'provenance.json', {'config': config, 'config_sha256': config_hash,
                'validation_report': str(validation_path.resolve()), 'rw': rw_meta,
                'source_acceptance_policy': validation['source_acceptance_policy'],
                'rw_accounting': rw_accounting, 'started_at': now()})
    role_table = pa.table({'namespace': [entry[0] for entry in role_ids],
                          'identifier': [entry[1] for entry in role_ids], 'role': [entry[2] for entry in role_ids]})
    local = threading.local()
    connections = []

    def worker_connection():
        if not hasattr(local, 'connection'):
            local.connection = duckdb.connect(config={'memory_limit': memory_limit, 'threads': threads,
                'temp_directory': str(release / 'spill' / str(threading.get_ident()))})
            connections.append(local.connection)
            local.connection.register('role_ids', role_table)
            local.connection.execute("CREATE MACRO normalized_doi(value) AS nullif(regexp_replace(lower(trim(url_decode(value))), '^https?://(dx[.])?doi[.]org/|^doi:[ ]*', ''), '')")
            local.connection.execute("CREATE MACRO normalized_pmid(value) AS nullif(regexp_replace(regexp_replace(value, '^https?://(www[.])?(pubmed[.]ncbi[.]nlm[.]nih[.]gov/|ncbi[.]nlm[.]nih[.]gov/pubmed/)', ''), '/$', ''), '')")
        return local.connection

    files = [entry for entry in json.loads((validation_path.parent / 'files.json').read_text()) if entry['entity'] == 'works']
    started = time.monotonic()
    def scan_one(entry):
        source_path = root / entry['key']
        stat = source_path.stat()
        if stat.st_size != entry['actual_bytes'] or stat.st_mtime_ns != entry['mtime_ns']:
            raise ValueError('Source file changed after validation: ' + entry['key'])
        shard = release / 'shards' / digest(entry['key'].encode())
        shard.mkdir(parents=True, exist_ok=True)
        checkpoint = shard / 'complete.json'
        fingerprint = digest(json.dumps(entry, sort_keys=True).encode())
        if checkpoint.exists() and json.loads(checkpoint.read_text()).get('fingerprint') == fingerprint:
            return
        connection = worker_connection()
        connection.read_parquet(str(source_path), hive_partitioning=False).create_view('source_work', replace=True)
        connection.execute('''CREATE OR REPLACE TEMP TABLE projected AS
            WITH identifiers AS (
                SELECT id, normalized_doi(doi) AS doi,
                    normalized_pmid(map_extract_value(ids, 'pmid')) AS pmid,
                    publication_year, publication_date, type, is_retracted, is_xpac, title
                FROM source_work
            ), evidence AS (
                SELECT *,
                    (doi IN (SELECT identifier FROM role_ids WHERE namespace='doi' AND role='original')
                     OR pmid IN (SELECT identifier FROM role_ids WHERE namespace='pmid' AND role='original')) IS TRUE AS original_evidence,
                    (doi IN (SELECT identifier FROM role_ids WHERE namespace='doi' AND role='notice')
                     OR pmid IN (SELECT identifier FROM role_ids WHERE namespace='pmid' AND role='notice')
                     OR type IN ('retraction', 'erratum')) IS TRUE AS notice_evidence,
                    regexp_matches(coalesce(title, ''), '(?i)^\\s*(retraction\\b|retracted\\b|withdrawal notice\\b|correction\\b|erratum\\b|corrigendum\\b|expression of concern\\b)') AS title_suspected
                FROM identifiers
            ) SELECT * EXCLUDE(title), CASE
                WHEN original_evidence AND notice_evidence THEN 'conflict'
                WHEN notice_evidence THEN 'known_notice'
                WHEN original_evidence THEN 'original_supported'
                WHEN title_suspected THEN 'suspected_notice'
                ELSE 'unresolved' END AS document_role
            FROM evidence''')
        for filename, query in {
            'cohorts.parquet': f'''SELECT is_xpac, type, publication_year, document_role, is_retracted,
                (publication_year BETWEEN 1 AND {int(validation['oa_snapshot_date'][:4])}
                 AND (publication_date IS NULL OR publication_date <= DATE '{validation['oa_snapshot_date']}')) IS TRUE AS date_eligible,
                count(*) AS work_count FROM projected GROUP BY ALL''',
            'identifiers.parquet': '''SELECT * FROM projected
                WHERE is_retracted IS TRUE OR original_evidence OR notice_evidence''',
            'targets.parquet': '''SELECT source_work.id, source_work.doi, source_work.publication_date,
                source_work.publication_year, source_work.type, source_work.is_xpac, source_work.is_retracted,
                source_work.authorships, source_work.authors_count, source_work.primary_topic,
                source_work.topics, source_work.primary_location, source_work.cited_by_count
                FROM source_work SEMI JOIN (
                    SELECT id FROM projected WHERE is_retracted IS TRUE OR original_evidence OR notice_evidence
                ) selected USING (id)''',
        }.items():
            destination = shard / filename
            temporary = str(destination) + '.tmp'
            connection.execute(f"COPY ({query}) TO '{temporary.replace(chr(39), chr(39) * 2)}' (FORMAT PARQUET, COMPRESSION ZSTD)")
            os.replace(temporary, destination)
        atomic_json(checkpoint, {'fingerprint': fingerprint, 'input_key': entry['key'], 'config_sha256': config_hash})
    print(f'Scanning with {workers} workers × {threads} threads; {memory_limit} per worker', flush=True)
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(scan_one, entry) for entry in files]
            for index, future in enumerate(as_completed(futures), 1):
                future.result()
                if index % 10 == 0:
                    print(f'Analyzed {index}/{len(files)} work files; {time.monotonic() - started:.0f}s', flush=True)
    finally:
        for connection in connections:
            connection.close()
    atomic_json(release / 'scan-complete.json', {'files': len(files), 'elapsed_seconds': time.monotonic() - started,
                                               'completed_at': now(), 'config_sha256': config_hash,
                                               'execution': {'workers': workers, 'threads_per_worker': threads, 'memory_per_worker': memory_limit}})
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validation-report', required=True)
    parser.add_argument('--rw-csv', required=True)
    parser.add_argument('--rw-source', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--memory-limit', default='32GB')
    parser.add_argument('--threads', type=int, default=6)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    release = scan_snapshot(args.validation_report, args.rw_csv, args.rw_source,
                            args.output_dir, args.memory_limit, args.threads, args.workers)
    print('Completed local scan: ' + str(release))


if __name__ == '__main__':
    main()
