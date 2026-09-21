import collections
import csv
import datetime
import hashlib
import json
from pathlib import Path

import duckdb

ROOT = Path('/home/ider/workspace/Scholarly-Retraction-Observatory')
BASE = Path('/tmp/retraction-kdocs-20260916')
OUT = BASE / 'event-year'
OUT.mkdir(exist_ok=True)
published = json.loads((BASE / 'published.json').read_text())
manifest = published['manifest']
for entry in manifest['files']:
    assert hashlib.sha256((ROOT / 'public' / entry['path']).read_bytes()).hexdigest() == entry['sha256']
source = Path('/mnt/hg02/openalex-snapshot/analysis/broad-runs') / manifest['scan_config_sha256']
papers = json.loads((source / 'rw_original.json').read_text())
matches = json.loads((source / 'rw_oa_match.json').read_text())
dates = collections.defaultdict(set)
matched = set()
invalid = set()
for paper in papers:
    identifier = matches[paper['id']]['selected_id']
    if not identifier:
        continue
    matched.add(identifier)
    try:
        value = datetime.date.fromisoformat(paper['retracted'])
    except (ValueError, TypeError):
        invalid.add(identifier)
        continue
    dates[identifier].add(value)
earliest = {identifier: min(values) for identifier, values in dates.items()}
connection = duckdb.connect(config={'threads': 32, 'memory_limit': '128GB'})
connection.execute('CREATE TABLE matched(id VARCHAR PRIMARY KEY)')
connection.executemany('INSERT INTO matched VALUES (?)', [(identifier,) for identifier in sorted(matched)])
connection.read_parquet(str(source / 'shards/*/identifiers.parquet')).create_view('identities')
connection.read_parquet(str(source / 'shards/*/targets.parquet')).create_view('targets')
records = connection.execute("""SELECT identities.id, identities.publication_year, identities.publication_date,
    targets.primary_topic.field.id, targets.primary_topic.subfield.id
    FROM identities JOIN matched USING(id) LEFT JOIN targets USING(id)
    WHERE identities.is_xpac IS FALSE AND identities.document_role IN ('original_supported','unresolved')
    AND identities.publication_year BETWEEN 1 AND 2026
    AND (identities.publication_date IS NULL OR identities.publication_date <= DATE '2026-06-26')""").fetchall()
works = {row[0]: row for row in records}
assert len(works) == len(records)
selected = {identifier for identifier in works if identifier in earliest and 2000 <= earliest[identifier].year <= 2025}
old_selected = {identifier for identifier, row in works.items() if identifier in earliest
    and earliest[identifier] <= datetime.date(2026, 6, 26) and 2000 <= row[1] <= 2025}
assert len(old_selected) == 59028
concept_directory = json.loads((source / 'concepts-complete.json').read_text())['directory']
connection.read_parquet(str(Path(concept_directory) / '*.parquet')).create_view('concept_records')
concepts = dict(connection.execute('SELECT id, concepts FROM concept_records JOIN matched USING(id)').fetchall())
assert set(works) <= set(concepts)
years = list(range(2000, 2026))
totals = collections.Counter(earliest[identifier].year for identifier in selected)
taxonomy = {item['id']: item for item in published['fields']['discipline_explorer']['taxonomies']}
groups = {'concepts_l0': ('concepts', 0), 'concepts_l1': ('concepts', 1), 'topics_field': ('topics', 1), 'topics_subfield': ('topics', 2)}
result = {}
evidence = []
for group, (system, level) in groups.items():
    nodes = {node['id']: node for node in taxonomy[system]['nodes'] if node['level'] == level and not node.get('missing') and not node.get('navigation_only')}
    counters = collections.defaultdict(collections.Counter)
    for identifier in selected:
        if system == 'concepts':
            labels = {concept['id'] for concept in (concepts[identifier] or []) if concept['level'] == level}
        else:
            label = works[identifier][3 if level == 1 else 4]
            labels = {label} if label else set()
        assert labels <= set(nodes), (group, labels - set(nodes))
        for label in labels or {'missing'}:
            counters[label][earliest[identifier].year] += 1
    ordered = sorted(nodes, key=lambda identifier: (-sum(counters[identifier].values()), identifier))
    result[group] = {'top6': ordered[:6], 'nodes': []}
    for identifier in ordered + ['missing']:
        node = {'id': identifier, 'label': nodes[identifier]['label'] if identifier != 'missing' else '分类缺失',
            'parents': nodes[identifier].get('parents', []) if identifier != 'missing' else [],
            'counts': [counters[identifier][year] for year in years]}
        node['total'] = sum(node['counts'])
        result[group]['nodes'].append(node)
        for year, numerator in zip(years, node['counts']):
            denominator = totals[year]
            assert 0 <= numerator <= denominator
            evidence.append({'system': group, 'id': identifier, 'label': node['label'], 'retraction_year': year,
                'n': numerator, 'N': denominator, 'percent': numerator / denominator * 100 if denominator else None})
        evidence.append({'system': group, 'id': identifier, 'label': node['label'], 'retraction_year': '2000-2025',
            'n': node['total'], 'N': len(selected), 'percent': node['total'] / len(selected) * 100})
    if system == 'topics':
        assert all(sum(node['counts'][index] for node in result[group]['nodes']) == totals[year] for index, year in enumerate(years))
for field in result['topics_field']['nodes']:
    if field['id'] == 'missing':
        continue
    children = [node for node in result['topics_subfield']['nodes'] if field['id'] in node['parents']]
    assert all(sum(node['counts'][index] for node in children) == field['counts'][index] for index in range(26))
summary = {'years': years, 'annual_denominators': [totals[year] for year in years], 'total': len(selected),
    'matched_works': len(matched), 'eligible_works': len(works),
    'eligible_no_valid_retraction_date': len(set(works) - set(earliest)),
    'eligible_earliest_before_2000': sum(earliest[identifier].year < 2000 for identifier in works if identifier in earliest),
    'eligible_earliest_after_2025': sum(earliest[identifier].year > 2025 for identifier in works if identifier in earliest),
    'multiple_distinct_valid_dates': sum(len(dates[identifier]) > 1 for identifier in selected),
    'publication_before_2000': sum(works[identifier][1] < 2000 for identifier in selected),
    'publication_after_2025': sum(works[identifier][1] > 2025 for identifier in selected),
    'publication_date_after_retraction': sum(bool(works[identifier][2] and works[identifier][2] > earliest[identifier]) for identifier in selected),
    'old_cohort_reconciled': len(old_selected), 'release_id': manifest['release_id'],
    'source_sha256': {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in ['rw_original.json','rw_oa_match.json','concepts-complete.json']},
    'method': 'Distinct eligible core Work; earliest valid matched RW retraction date, 2000-2025; no publication cohort restriction; taxonomy at OA snapshot 2026-06-26; RW snapshot 2026-09-10.',
    'checks': ['published hashes', 'old cohort 59028 reconciliation', 'unique Work identities', 'all selected concept rows present', 'all attached category IDs recognized', 'n<=N', 'Topic annual partitions incl missing', 'Subfield annual sums equal Field']}
assert summary['eligible_works'] == summary['total'] + summary['eligible_no_valid_retraction_date'] + summary['eligible_earliest_before_2000'] + summary['eligible_earliest_after_2025']
(OUT / 'analysis.json').write_text(json.dumps({'summary': summary, 'groups': result}, ensure_ascii=False, indent=2))
with (OUT / 'all-subjects.csv').open('w', newline='', encoding='utf-8-sig') as handle:
    writer = csv.DictWriter(handle, fieldnames=list(evidence[0]))
    writer.writeheader()
    writer.writerows(evidence)
print(json.dumps(summary, ensure_ascii=False, indent=2))
for group, content in result.items():
    print(group, [(node['label'], node['total']) for node in content['nodes'][:6]])
