"""Reproducible, bounded examples from the frozen screening population."""

import argparse
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path

SEED = 'screening-examples-v1'
ROOT = Path(__file__).resolve().parents[1]


def exclusion(record, cutoff):
    if record['type'] != 'article':
        return 'excluded_work_type'
    if record['document_role'] not in ('original_supported', 'unresolved'):
        return 'excluded_' + record['document_role']
    if not record['publication_year'] or not 1 <= record['publication_year'] <= int(cutoff[:4]) or (record['publication_date'] and str(record['publication_date']) > cutoff):
        return 'excluded_date'
    return 'retained_A1'


def generate(run_dir):
    import duckdb

    provenance = json.loads((run_dir / 'provenance.json').read_text())
    validation_path = Path(provenance['validation_report'])
    validation = json.loads(validation_path.read_text())
    complete = json.loads((run_dir / 'scan-complete.json').read_text())
    if complete['config_sha256'] != provenance['config_sha256']:
        raise ValueError('Scan provenance mismatch')
    entries = [entry for entry in json.loads((validation_path.parent / 'files.json').read_text()) if entry['entity'] == 'works']
    if len(entries) != complete['files']:
        raise ValueError('Incomplete manifest-scoped scan')
    shard_sources = {hashlib.sha256(entry['key'].encode()).hexdigest(): entry for entry in entries}
    for key in shard_sources:
        marker = json.loads((run_dir / 'shards' / key / 'complete.json').read_text())
        if marker['config_sha256'] != provenance['config_sha256']:
            raise ValueError('Shard belongs to another scan configuration')
    paths = [str(run_dir / 'shards' / key / 'identifiers.parquet') for key in shard_sources]
    with duckdb.connect(config={'threads': 4, 'memory_limit': '4GB'}) as connection:
        connection.read_parquet(paths, filename=True, hive_partitioning=False).create_view('records')
        cursor = connection.execute('SELECT * FROM records WHERE is_xpac IS FALSE AND is_retracted IS TRUE')
        columns = [column[0] for column in cursor.description]
        counts, strata, selected = Counter(), Counter(), {}
        for values in cursor.fetchall():
            record = dict(zip(columns, values))
            reason = exclusion(record, validation['oa_snapshot_date'])
            counts[reason] += 1
            if reason == 'retained_A1':
                continue
            stratum = reason + ('_review' if record['type'] == 'review' else '_other') if reason == 'excluded_work_type' else reason
            strata[stratum] += 1
            record.update(exclusion=reason, stratum=stratum)
            rank = hashlib.sha256((SEED + '/' + record['id']).encode()).hexdigest()
            selected[stratum] = sorted([*selected.get(stratum, []), (rank, record)], key=lambda item: item[0])[:2]
        examples = [record for stratum in sorted(selected) for rank, record in selected[stratum]]
        if len(examples) > 12:
            raise ValueError('Sample cap exceeded; review new screening categories')
        for record in examples:
            source = shard_sources[Path(record.pop('filename')).parent.name]
            path = Path(validation['snapshot_dir']) / source['key']
            stat = path.stat()
            if stat.st_size != source['actual_bytes'] or stat.st_mtime_ns != source['mtime_ns']:
                raise ValueError('Snapshot file changed since validation')
            connection.read_parquet(str(path), hive_partitioning=False).create_view('source_work', replace=True)
            found = connection.execute('SELECT title FROM source_work WHERE id = ?', [record['id']]).fetchall()
            if len(found) != 1:
                raise ValueError('Sample Work identity is not unique')
            record['title'] = found[0][0]
            record['publication_date'] = str(record['publication_date']) if record['publication_date'] else None
    return {'schema_version': 1, 'sampling_version': SEED, 'sampled_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'oa_snapshot_date': validation['oa_snapshot_date'], 'rw_snapshot_date': provenance['rw']['rw_snapshot_date'],
            'oa_manifest_sha256': validation['manifest_sha256'], 'scan_config_sha256': provenance['config_sha256'],
            'role_policy_version': provenance['config']['role_policy'], 'screening_counts': dict(sorted(counts.items())),
            'stratum_counts': dict(sorted(strata.items())), 'sample_count': len(examples), 'items': examples}


def reassess(data, broad_dir):
    import duckdb

    provenance = json.loads((broad_dir / 'provenance.json').read_text())
    if provenance['config']['role_policy'] != 'original-first-independent-notices-v2':
        raise ValueError('Expected the independently staged broad policy run')
    with duckdb.connect(config={'threads': 4, 'memory_limit': '4GB'}) as connection:
        connection.read_parquet(str(broad_dir / 'shards/*/identifiers.parquet')).create_view('current_records')
        counts = connection.execute('''SELECT document_role, publication_year, publication_date, count(*)
            FROM current_records WHERE is_xpac IS FALSE AND is_retracted IS TRUE GROUP BY ALL''').fetchall()
        screening = Counter()
        for role, year, date, count in counts:
            reason = 'excluded_known_notice' if role == 'known_notice' else 'excluded_date' if not year or not 1 <= year <= int(data['oa_snapshot_date'][:4]) or (date and str(date) > data['oa_snapshot_date']) else 'retained_A1'
            screening[reason] += count
        for row in data['items']:
            found = connection.execute('SELECT document_role, linked_distinct_originals FROM current_records WHERE id = ?', [row['id']]).fetchall()
            if len(found) != 1:
                raise ValueError('Reassessment must identify exactly one Work')
            role, originals = found[0]
            valid_date = bool(row['publication_year'] and 1 <= row['publication_year'] <= int(data['oa_snapshot_date'][:4]) and (not row['publication_date'] or row['publication_date'] <= data['oa_snapshot_date']))
            row.update(linked_distinct_originals=originals,
                       current_outcome='excluded_known_notice' if role == 'known_notice' else 'retained_A1' if valid_date else 'excluded_date')
    return {**data, 'schema_version': 2, 'sampling_version': 'legacy-screening-reassessment-v2',
            'legacy_scan_config_sha256': data['scan_config_sha256'], 'legacy_role_policy_version': data['role_policy_version'],
            'screening_counts': dict(screening),
            'scan_config_sha256': provenance['config_sha256'], 'role_policy_version': provenance['config']['role_policy']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    parser.add_argument('--broad-run', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'public/data/screening-examples.json')
    parser.add_argument('--contract-output', type=Path, default=ROOT / 'src/report/screeningExamplesAsset.js')
    args = parser.parse_args()
    result = generate(args.run_dir)
    if args.broad_run:
        result = reassess(result, args.broad_run)
    raw = (json.dumps(result, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode()
    args.output.write_bytes(raw)
    contract = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    args.contract_output.write_text('export const screeningExamplesAsset = ' + json.dumps(contract) + ';\n')
    print(json.dumps({'sample_count': result['sample_count'], 'screening_counts': result['screening_counts'], 'asset': contract}, ensure_ascii=False))
