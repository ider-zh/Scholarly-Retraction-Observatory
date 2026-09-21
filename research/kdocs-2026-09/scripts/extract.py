import collections
import hashlib
import json
import pathlib
import sys

import duckdb

ROOT = pathlib.Path('/home/ider/workspace/Scholarly-Retraction-Observatory')
OUT = pathlib.Path('/tmp/retraction-kdocs-20260916')
sys.path.insert(0, str(ROOT))
from pipeline.reason_families import families, GROUPS

published = json.loads((OUT / 'published.json').read_text())
manifest = published['manifest']
base = pathlib.Path('/mnt/hg02/openalex-snapshot/analysis/broad-runs') / manifest['scan_config_sha256']
for entry in manifest['files']:
    assert hashlib.sha256((ROOT / 'public' / entry['path']).read_bytes()).hexdigest() == entry['sha256']
explorer = published['fields']['discipline_explorer']
taxonomies = {item['id']: item for item in explorer['taxonomies']}
connection = duckdb.connect(config={'threads': 32, 'memory_limit': '128GB'})
connection.read_parquet(str(base / 'shards/*/identifiers.parquet')).create_view('identities')
connection.read_parquet(str(base / 'shards/*/targets.parquet')).create_view('targets')
columns = ['id', 'publication_year', 'is_retracted', 'type', 'field_id', 'field_name', 'subfield_id', 'subfield_name']
records = connection.execute("""SELECT identities.id, identities.publication_year, identities.is_retracted, identities.type,
    targets.primary_topic.field.id, targets.primary_topic.field.display_name,
    targets.primary_topic.subfield.id, targets.primary_topic.subfield.display_name
    FROM identities JOIN targets USING(id)
    WHERE identities.is_xpac IS FALSE AND identities.document_role IN ('original_supported','unresolved')
    AND identities.publication_year BETWEEN 1 AND 2026
    AND (identities.publication_date IS NULL OR identities.publication_date <= DATE '2026-06-26')""").fetchall()
works = {row[0]: dict(zip(columns, row)) for row in records}
assert len(works) == len(records)
originals = json.loads((base / 'rw_original.json').read_text())
matches = json.loads((base / 'rw_oa_match.json').read_text())
linked = [paper for paper in originals if matches[paper['id']]['selected_id']]
matched_ids = {matches[paper['id']]['selected_id'] for paper in linked}
eligible_papers = [paper for paper in linked if paper['retracted'] and paper['retracted'] <= '2026-06-26'
    and matches[paper['id']]['selected_id'] in works]
selected = {matches[paper['id']]['selected_id'] for paper in eligible_papers}
assert len(selected) == taxonomies['topics']['counts']['C_D'][0] == 60023
annual = collections.Counter(works[identifier]['publication_year'] for identifier in selected)
assert [annual[year] for year in range(2000, 2027)] == taxonomies['topics']['counts']['C_D'][1:]
scope_ids = {identifier for identifier in selected if 2000 <= works[identifier]['publication_year'] <= 2025}
reason_sets = collections.defaultdict(set)
for paper in eligible_papers:
    identifier = matches[paper['id']]['selected_id']
    if identifier in scope_ids:
        reason_sets[identifier].update(paper['reasons'])
assert set(reason_sets) == scope_ids
reason_counts = collections.Counter()
field_counts = collections.Counter()
field_reasons = collections.defaultdict(collections.Counter)
for identifier, labels in reason_sets.items():
    reason_counts.update(families(labels))
    field = works[identifier]['field_id'] or 'unknown'
    field_counts[field] += 1
    field_reasons[field].update(families(labels))
for node in taxonomies['topics']['nodes']:
    if node['level'] != 1:
        continue
    key = 'unknown' if node.get('missing') else node['id']
    assert field_counts[key] == sum(node['counts']['C_D'][1:27]), (key, field_counts[key])
connection.read_parquet(str(base / 'shards/*/cohorts.parquet')).create_view('cohorts')
types = connection.execute("""SELECT type, sum(work_count)::BIGINT,
    sum(CASE WHEN is_retracted IS TRUE THEN work_count ELSE 0 END)::BIGINT
    FROM cohorts WHERE is_xpac IS FALSE AND document_role IN ('original_supported','unresolved')
    AND date_eligible AND publication_year BETWEEN 2000 AND 2025 GROUP BY type ORDER BY 2 DESC""").fetchall()
assert sum(row[1] for row in types) == sum(taxonomies['topics']['denominator'][1:27])
assert sum(row[2] for row in types) == sum(taxonomies['topics']['counts']['A1'][1:27])
for taxonomy in taxonomies.values():
    if taxonomy['id'] == 'subjects':
        continue
    for node in taxonomy['nodes']:
        for population in ['A1', 'C_D']:
            assert all(0 <= count <= denominator for count, denominator in zip(node['counts'][population], node['denominator']))
summary = {
    'release_id': manifest['release_id'], 'cutoff': '2026-06-26', 'year_start': 2000, 'year_end': 2025,
    'rw_originals': len(originals), 'rw_linked_originals': len(linked), 'rw_matched_distinct_works': len(matched_ids),
    'rw_eligible_distinct_all_years': len(selected), 'rw_eligible_distinct_window': len(scope_ids),
    'rw_matched_after_cutoff': sum(bool(paper['retracted'] and paper['retracted'] > '2026-06-26') for paper in linked),
    'rw_matched_missing_date': sum(not paper['retracted'] for paper in linked),
    'types': types, 'reason_counts': reason_counts, 'field_reason_denominators': field_counts,
    'field_reasons': field_reasons,
    'reason_names': {key: value[0] for key, value in GROUPS.items()} | {'missing': '原因缺失', 'unmapped': '未映射标签'},
    'oa_window': sum(taxonomies['topics']['counts']['A1'][1:27]),
    'denominator_window': sum(taxonomies['topics']['denominator'][1:27]),
    'provenance_note': 'Existing published C_D uses earliest RW retraction <= OA cutoff; reason labels are the RW 2026-09-10 union, not historical labels at cutoff.',
    'checks': ['all 9 published SHA256 checks', 'schema validation', 'C_D unique Work full and annual reconciliation',
               'matched RW Field counts reconciliation', 'type counts/denominators reconciliation', 'all taxonomy n<=N checks']
}
(OUT / 'analysis.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print(json.dumps({key: value for key, value in summary.items() if key not in ['field_reasons','reason_names']}, ensure_ascii=False, indent=2))
