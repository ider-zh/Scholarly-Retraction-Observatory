"""Create an isolated broad-policy run from immutable canonical scan evidence."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil

import pyarrow as pa
import pyarrow.parquet as pq

from .validate_snapshot import atomic_json, digest, now
from .work_policy import VERSION, METHOD, classify, notice_links


def derive(source_dir, output_dir, workers=8):
    source_dir, output_dir = Path(source_dir).resolve(), Path(output_dir).resolve()
    if output_dir == source_dir or output_dir.is_relative_to(source_dir):
        raise ValueError('Broad-policy output must not overwrite the original run')
    provenance = json.loads((source_dir / 'provenance.json').read_text())
    complete = json.loads((source_dir / 'scan-complete.json').read_text())
    validation_path = Path(provenance['validation_report'])
    validation = json.loads(validation_path.read_text())
    entries = [entry for entry in json.loads((validation_path.parent / 'files.json').read_text()) if entry['entity'] == 'works']
    if validation['status'] != 'validated' or validation['blockers'] or complete['config_sha256'] != provenance['config_sha256'] or len(entries) != complete['files']:
        raise ValueError('Incomplete or unvalidated source run')
    config = {**provenance['config'], 'role_policy': VERSION, 'parent_scan_config_sha256': provenance['config_sha256'],
              'derivation_sha256': digest(Path(__file__).read_bytes()), 'work_policy_sha256': digest(Path(__file__).with_name('work_policy.py').read_bytes())}
    config_hash = digest(json.dumps(config, sort_keys=True).encode())
    destination = output_dir / config_hash
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('rw_original.json', 'rw_notice.json'):
        shutil.copyfile(source_dir / name, destination / name)
    links = notice_links(json.loads((source_dir / 'rw_notice.json').read_text()))
    atomic_json(destination / 'provenance.json', {**provenance, 'config': config, 'config_sha256': config_hash,
                'parent_run': str(source_dir), 'work_policy_method': METHOD, 'started_at': now()})

    def process(entry):
        key = digest(entry['key'].encode())
        original, target = source_dir / 'shards' / key, destination / 'shards' / key
        marker = json.loads((original / 'complete.json').read_text())
        if marker['config_sha256'] != provenance['config_sha256']:
            raise ValueError('Wrong source shard configuration')
        target.mkdir(parents=True, exist_ok=True)
        cohort_table = pq.read_table(original / 'cohorts.parquet')
        columns = [name for name in cohort_table.column_names if name != 'work_count']
        totals = Counter()
        for row in cohort_table.to_pylist():
            row['document_role'] = 'original_supported' if row['document_role'] == 'original_supported' else 'unresolved'
            totals[tuple(row[name] for name in columns)] += row['work_count']
        identities = pq.read_table(original / 'identifiers.parquet')
        rows = identities.to_pylist()
        changes = Counter()
        for row in rows:
            previous = row['document_role']
            mapped = 'original_supported' if previous == 'original_supported' else 'unresolved'
            role, uncertain, distinct = classify(row, links)
            year, publication_date = row['publication_year'], row['publication_date']
            valid_date = bool(year and 1 <= year <= int(validation['oa_snapshot_date'][:4]) and (publication_date is None or str(publication_date) <= validation['oa_snapshot_date']))
            cohort = {**row, 'document_role': mapped, 'date_eligible': valid_date}
            totals[tuple(cohort[name] for name in columns)] -= 1
            cohort['document_role'] = role
            totals[tuple(cohort[name] for name in columns)] += 1
            row.update(document_role=role, legacy_document_role=previous, screening_uncertain=uncertain,
                       linked_distinct_originals=distinct)
            if row['is_xpac'] is False and row['is_retracted'] is True:
                changes[(previous, role)] += 1
        if any(value < 0 for value in totals.values()) or sum(totals.values()) != sum(cohort_table['work_count'].to_pylist()):
            raise ValueError('Cohort transformation failed conservation')
        schema = identities.schema.append(pa.field('legacy_document_role', pa.string())).append(pa.field('screening_uncertain', pa.bool_())).append(pa.field('linked_distinct_originals', pa.list_(pa.string())))
        pq.write_table(pa.Table.from_pylist(rows, schema=schema), target / 'identifiers.parquet', compression='zstd')
        pq.write_table(pa.Table.from_pylist([{**dict(zip(columns, key)), 'work_count': count} for key, count in totals.items() if count], schema=cohort_table.schema), target / 'cohorts.parquet', compression='zstd')
        if not (target / 'targets.parquet').exists():
            os.link(original / 'targets.parquet', target / 'targets.parquet')
        atomic_json(target / 'complete.json', {**marker, 'config_sha256': config_hash, 'parent_config_sha256': provenance['config_sha256'], 'role_policy': VERSION})
        return changes

    changes = Counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for index, result in enumerate(executor.map(process, entries), 1):
            changes.update(result)
            if index % 250 == 0:
                print(f'Broad role derivation: {index}/{len(entries)}', flush=True)
    atomic_json(destination / 'scan-complete.json', {**complete, 'config_sha256': config_hash, 'completed_at': now(), 'role_policy': VERSION})
    atomic_json(destination / 'policy-audit.json', {'policy': VERSION, 'method': METHOD,
                'transitions': [{'old_role': old, 'new_role': new, 'count': count} for (old, new), count in sorted(changes.items())]})
    print(destination, flush=True)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_dir', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    derive(args.source_dir, args.output_dir, args.workers)
