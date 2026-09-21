import argparse
from collections import Counter, defaultdict
import datetime
import json
from pathlib import Path

import duckdb


def main():
    parser = argparse.ArgumentParser(description='Read-only audit of the September 2026 matched sample.')
    parser.add_argument('--snapshot-root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--threads', type=int, default=32)
    parser.add_argument('--memory-limit', default='128GB')
    arguments = parser.parse_args()
    manifest = json.loads(arguments.manifest.read_text())
    cutoff = datetime.date.fromisoformat(manifest['oa_snapshot_date'])
    source = arguments.snapshot_root / 'analysis/broad-runs' / manifest['scan_config_sha256']
    papers = json.loads((source / 'rw_original.json').read_text())
    matches = json.loads((source / 'rw_oa_match.json').read_text())
    identifiers = sorted({entry['selected_id'] for entry in matches.values() if entry['selected_id']})
    dates = defaultdict(set)
    for paper in papers:
        identifier = matches[paper['id']]['selected_id']
        if identifier:
            try:
                dates[identifier].add(datetime.date.fromisoformat(paper['retracted']))
            except (ValueError, TypeError):
                pass
    earliest = {identifier: min(values) for identifier, values in dates.items()}
    with duckdb.connect(config={'threads': arguments.threads, 'memory_limit': arguments.memory_limit}) as connection:
        connection.read_parquet(str(source / 'shards/*/identifiers.parquet')).create_view('identities')
        rows = connection.execute('''SELECT id,is_xpac,document_role,publication_year,publication_date
            FROM identities WHERE id IN (SELECT unnest(?))''', [identifiers]).fetchall()
    if len(rows) != len(identifiers) or len({row[0] for row in rows}) != len(identifiers):
        raise ValueError('Matched identities are missing or duplicated.')
    excluded = Counter()
    eligible = set()
    for identifier, expansion, role, year, publication_date in rows:
        reasons = []
        if expansion is not False:
            reasons.append('outside_core')
        if role not in ('original_supported', 'unresolved'):
            reasons.append('document_role')
        if year is None or not 1 <= year <= cutoff.year:
            reasons.append('publication_year')
        if publication_date and publication_date > cutoff:
            reasons.append('publication_date_after_snapshot')
        if reasons:
            excluded['+'.join(reasons)] += 1
        else:
            eligible.add(identifier)
    event_partition = Counter()
    for identifier in eligible:
        if identifier not in earliest:
            event_partition['missing_parseable_rw_date'] += 1
        elif earliest[identifier].year < 2000:
            event_partition['before_2000'] += 1
        elif earliest[identifier].year > 2025:
            event_partition['after_2025'] += 1
        else:
            event_partition['included_2000_2025'] += 1
    if sum(excluded.values()) + len(eligible) != len(identifiers):
        raise ValueError('Eligibility partition does not reconcile.')
    if sum(event_partition.values()) != len(eligible):
        raise ValueError('RW event date partition does not reconcile.')
    print(json.dumps({'oa_snapshot_date': manifest['oa_snapshot_date'],
        'rw_snapshot_date': manifest['rw_snapshot_date'], 'rw_originals': len(papers),
        'matching_outcomes': dict(Counter(entry['match_outcome'] for entry in matches.values())),
        'distinct_matched_works': len(identifiers), 'eligibility_exclusions': dict(excluded),
        'eligible_works': len(eligible), 'rw_event_date_partition': dict(event_partition)},
        ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
