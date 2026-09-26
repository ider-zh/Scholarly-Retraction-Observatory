import argparse
import base64
import concurrent.futures
import datetime
import hashlib
import json
import os
import threading
import zlib
from pathlib import Path

import duckdb
import pyarrow as arrow
import pyarrow.parquet as parquet


ROOT = Path('/mnt/hg02/openalex-snapshot/analysis')
OUTPUT = ROOT / 'retraction-disruption-ngd/20260925'
BROAD = ROOT / 'broad-runs/c05efc0d85c4b20e357f558120235726d6faf69ebe397e6999901c92f720ca87'
RUN = ROOT / 'disruption/full-runs/aa3884a2c445ca56fa6258f46e103e80dbbd382002f2eb3bd362d5066ea7777e'
FOUNDATION = ROOT / 'disruption/foundation/10c1785b4a6f9757823fc6dd005a052716e2c510ea751659cab4bcfba4c35e2a/83e931fc4d8da8f2c7d90a3e7f4e2c86504b6ed4fa0cb735a7d64ccdbf7b3fe6'
MEMBERSHIP = ROOT / 'taxonomy-ngd/46194db71c3b1c538ce87257994318307a066c9708ca9038d8a0d48233ba9319/staging'
PUBLISHED_FIELDS = Path(__file__).resolve().parents[2] / 'public/data/snapshot/fields.json'
CODE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
POLICIES = [('ex', 'exclude_publication_year'), ('in', 'include_publication_year')]
VARIANTS = [
    ('main_cd5_r10_c5', 'ex', '5y', 10, 5, 'cd'),
    ('cd5_no_extra_threshold', 'ex', '5y', 1, 0, 'cd'),
    ('cd5_r5_c5', 'ex', '5y', 5, 5, 'cd'),
    ('cd5_r20_c5', 'ex', '5y', 20, 5, 'cd'),
    ('cd5_r10_c0', 'ex', '5y', 10, 0, 'cd'),
    ('cd5_r10_c10', 'ex', '5y', 10, 10, 'cd'),
    ('cd3_r10_c5', 'ex', '3y', 10, 5, 'cd'),
    ('cd10_r10_c5', 'ex', '10y', 10, 5, 'cd'),
    ('cd_lifetime_r10_c5', 'ex', 'lifetime', 10, 5, 'cd'),
    ('cd5_include_year_r10_c5', 'in', '5y', 10, 5, 'cd'),
    ('no_nr5_r10_c5', 'ex', '5y', 10, 5, 'no_nr'),
]


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def connection(threads=24, memory='192GB'):
    spill = OUTPUT / 'spill' / f'{os.getpid()}-{threading.get_ident()}'
    spill.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(config={'threads': threads, 'memory_limit': memory,
                                 'temp_directory': str(spill),
                                 'preserve_insertion_order': False})


def validate_cache(path):
    if not path.exists():
        return False
    footer = parquet.ParquetFile(path).metadata
    if footer.num_columns == 0:
        raise ValueError('Invalid cached schema: ' + str(path))
    return True


def initialize_run(output):
    inputs = [RUN / 'completion.json', RUN / 'analytical/manifest.json',
              BROAD / 'provenance.json', BROAD / 'rw_original.json', BROAD / 'rw_oa_match.json',
              MEMBERSHIP.parent / 'definition.json.gz']
    config = {'version': 'cross-disruption-v1', 'variants': VARIANTS,
              'oa_years': [2000, 2025], 'rw_event_years': [2000, 2025],
              'snapshot': '2026-06-26',
              'inputs': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}}
    config = json.loads(json.dumps(config))
    marker = output / 'disruption_config.json'
    if marker.exists():
        if json.loads(marker.read_text()) != config:
            raise ValueError('Source or configuration changed; choose a new output directory')
    else:
        write_json(marker, config)


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    temporary.replace(path)


def copy(connection, query, destination):
    temporary = destination.with_suffix('.partial.parquet')
    connection.execute(f'COPY ({query}) TO {literal(temporary)} (FORMAT PARQUET, COMPRESSION ZSTD)')
    temporary.replace(destination)


def rw_dates():
    originals = json.loads((BROAD / 'rw_original.json').read_text())
    matches = json.loads((BROAD / 'rw_oa_match.json').read_text())
    dates = {}
    for paper in originals:
        identifier = matches[paper['id']]['selected_id']
        if not identifier:
            continue
        try:
            date = datetime.date.fromisoformat(paper['retracted'])
        except (TypeError, ValueError):
            continue
        dates[identifier] = min(dates.get(identifier, date), date)
    return dates


def cohort(output):
    destination = output / 'cohort.parquet'
    if validate_cache(destination):
        return
    database = connection()
    database.execute('CREATE TABLE rw_dates(work_id VARCHAR PRIMARY KEY, retraction_date DATE)')
    database.executemany('INSERT INTO rw_dates VALUES (?, ?)', list(rw_dates().items()))
    database.execute(f"CREATE VIEW identities AS SELECT id AS work_id, document_role FROM read_parquet({literal(BROAD / 'shards/*/identifiers.parquet')})")
    database.execute(f"CREATE VIEW metadata AS SELECT * FROM read_parquet({literal(FOUNDATION / 'shards/*/nodes.parquet')})")
    database.execute(f"CREATE VIEW membership AS SELECT work_id_numeric, concept_l0_ids, concept_l1_ids FROM read_parquet({literal(MEMBERSHIP / 'part-*/membership.parquet')})")
    print('Building aligned OA and RW cohorts', flush=True)
    database.execute('''CREATE TABLE selected AS
      SELECT metadata.work_id, work_id_numeric, publication_year, publication_date, work_type,
        is_retracted IS TRUE AS is_retracted, field_id, subfield_id,
        publication_year BETWEEN 2000 AND 2025 AS in_oa,
        coalesce(year(retraction_date) BETWEEN 2000 AND 2025, false) AS in_rw,
        retraction_date,
        publication_date > retraction_date AS publication_after_retraction
      FROM metadata LEFT JOIN identities USING(work_id) LEFT JOIN rw_dates USING(work_id)
      WHERE is_xpac IS FALSE
        AND coalesce(document_role, 'unresolved') IN ('original_supported','unresolved')
        AND publication_year BETWEEN 1 AND 2026
        AND (publication_date IS NULL OR publication_date <= DATE '2026-06-26')
        AND (publication_year BETWEEN 2000 AND 2025 OR year(retraction_date) BETWEEN 2000 AND 2025)''')
    counts = database.execute('SELECT count(*) FILTER(WHERE in_oa), count(*) FILTER(WHERE in_oa AND is_retracted), count(*) FILTER(WHERE in_rw), count(*), count(DISTINCT work_id_numeric) FROM selected').fetchone()
    assert counts[:3] == (220305891, 77414, 58345), counts
    assert counts[3] == counts[4]
    copy(database, 'SELECT selected.*, concept_l0_ids, concept_l1_ids FROM selected LEFT JOIN membership USING(work_id_numeric)', destination)
    assert database.execute(f'SELECT count(*) FROM read_parquet({literal(destination)})').fetchone()[0] == counts[3]
    write_json(output / 'cohort.json', {'counts': dict(zip(['oa', 'oa_retracted', 'rw', 'union', 'unique'], counts)), 'source': str(BROAD), 'metadata': str(FOUNDATION), 'membership': str(MEMBERSHIP), 'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat()})
    database.close()


def rw_labels(output):
    destination = output / 'rw_topic_labels.parquet'
    if validate_cache(destination):
        return
    database = connection(4, '16GB')
    database.register('dates', arrow.Table.from_pylist([{'work_id': identifier, 'retraction_date': date} for identifier, date in rw_dates().items()]))
    database.execute(f"CREATE VIEW identities AS SELECT * FROM read_parquet({literal(BROAD / 'shards/*/identifiers.parquet')})")
    database.execute(f"CREATE VIEW targets AS SELECT id, primary_topic FROM read_parquet({literal(BROAD / 'shards/*/targets.parquet')})")
    database.execute(f"CREATE TABLE observed AS SELECT * FROM read_parquet({literal(output / 'cohort.parquet')}) WHERE in_rw")
    database.execute('''CREATE TABLE expected AS SELECT identities.id AS work_id,
      primary_topic.field.id AS rw_field_id, primary_topic.subfield.id AS rw_subfield_id
      FROM identities JOIN dates ON identities.id=dates.work_id LEFT JOIN targets USING(id)
      WHERE is_xpac IS FALSE AND document_role IN ('original_supported','unresolved')
        AND publication_year BETWEEN 1 AND 2026
        AND (publication_date IS NULL OR publication_date <= DATE '2026-06-26')
        AND year(retraction_date) BETWEEN 2000 AND 2025''')
    assert database.execute('SELECT count(*),count(DISTINCT work_id) FROM expected').fetchone() == (58345, 58345)
    difference = database.execute('SELECT count(*) FROM ((SELECT work_id FROM expected EXCEPT SELECT work_id FROM observed) UNION ALL (SELECT work_id FROM observed EXCEPT SELECT work_id FROM expected))').fetchone()[0]
    assert difference == 0, difference
    changes = database.execute('''SELECT work_id, field_id AS oa_field_id, subfield_id AS oa_subfield_id,
      rw_field_id, rw_subfield_id FROM observed JOIN expected USING(work_id)
      WHERE field_id IS DISTINCT FROM rw_field_id OR subfield_id IS DISTINCT FROM rw_subfield_id''').fetchall()
    assert len(changes) == 84, len(changes)
    copy(database, 'SELECT * FROM expected', destination)
    write_json(output / 'rw_topic_label_audit.json', {'version': 'preserve-historical-rw-primary-topic-v1',
      'rw_work_id_symmetric_difference': difference, 'rw_rows': 58345, 'changed_label_works': len(changes),
      'policy': 'OA uses foundation primary_topic; RW uses the historical broad targets primary_topic. Neither source is rewritten; all CD values are unchanged.',
      'columns': ['work_id', 'oa_field_id', 'oa_subfield_id', 'rw_field_id', 'rw_subfield_id'],
      'differences': changes, 'labels_sha256': hashlib.sha256(destination.read_bytes()).hexdigest()})
    database.close()


def cohort_view(database, output, source):
    database.execute(f'''CREATE OR REPLACE VIEW cohort AS SELECT source.*, labels.rw_field_id, labels.rw_subfield_id
      FROM read_parquet({literal(source)}) source LEFT JOIN read_parquet({literal(output / 'rw_topic_labels.parquet')}) labels USING(work_id)''')


def scalar_query(focal, windows):
    expressions = ['focal.work_id', 'max(reference_count_valid) AS reference_count']
    for short, policy in POLICIES:
        for window in ['3y', '5y', '10y', 'lifetime']:
            condition = f"window_policy={literal(policy)} AND windows.window={literal(window)}"
            for source, target in [('disruption_cd', 'cd'), ('disruption_no_nr', 'no_nr'), ('citation_count', 'citations'), ('is_mature', 'mature'), ('planned_end_date', 'end')]:
                expressions.append(f'max({source}) FILTER(WHERE {condition}) AS {target}_{short}_{window}')
    return f"SELECT {', '.join(expressions)} FROM read_parquet({literal(focal)}) focal JOIN read_parquet({literal(windows)}) windows USING(work_id) WHERE reference_count_valid > 0 GROUP BY focal.work_id"


def scalar(output, workers=8):
    destination = output / 'scalar'
    destination.mkdir(exist_ok=True)
    sources = sorted((RUN / 'analytical/partitions').glob('part-*'))

    def process(source):
        target = destination / (source.name + '.parquet')
        if validate_cache(target):
            return
        database = connection(3, '16GB')
        copy(database, scalar_query(source / 'focal.parquet', source / 'windows.parquet'), target)
        database.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        for index, _ in enumerate(executor.map(process, sources), 1):
            if index % 100 == 0:
                print(f'Scalar cache {index}/{len(sources)}', flush=True)
    write_json(output / 'scalar.json', {'partitions': len(sources), 'source': str(RUN), 'selection': 'reference_count_valid > 0; all 8 standard windows retained; interpreted CD/null semantics unchanged'})


def membership_sql(taxonomy):
    if taxonomy in ['concepts_l0', 'concepts_l1']:
        column = 'concept_l0_ids' if taxonomy == 'concepts_l0' else 'concept_l1_ids'
        return f"SELECT *, subject_id AS rw_subject_id FROM (SELECT *, unnest(list_distinct({column})) AS subject_id FROM cohort)"
    column = 'field_id' if taxonomy == 'topics_field' else 'subfield_id'
    return f'SELECT *, {column} AS subject_id, rw_{column} AS rw_subject_id FROM cohort WHERE {column} IS NOT NULL OR rw_{column} IS NOT NULL'


def variant_expression(variant):
    name, short, window, references, citations, metric = variant
    value = f'{metric}_{short}_{window}'
    maturity = 'true' if window == 'lifetime' else f'mature_{short}_{window} IS TRUE'
    return f'CASE WHEN reference_count >= {references} AND citations_{short}_{window} >= {citations} AND {maturity} THEN {value} END'


def baseline(output):
    database = connection()
    cohort_view(database, output, output / 'cohort.parquet')
    destination = output / 'aggregates'
    destination.mkdir(exist_ok=True)
    rw_audit = database.execute('''SELECT count(*) AS total,
      count(*) FILTER(WHERE publication_after_retraction) AS publication_after_retraction,
      count(*) FILTER(WHERE publication_date IS NULL) AS publication_date_missing,
      count(*) FILTER(WHERE make_date(publication_year + 5,12,31) < retraction_date
        AND publication_after_retraction IS NOT TRUE) AS five_year_window_ends_before_retraction,
      count(*) FILTER(WHERE in_oa) AS in_oa_publication_cohort
      FROM cohort WHERE in_rw''').fetchone()
    write_json(output / 'rw_temporal_audit.json', dict(zip(['total', 'publication_after_retraction', 'publication_date_missing', 'five_year_window_ends_before_retraction', 'in_oa_publication_cohort'], rw_audit)))
    if not validate_cache(output / 'global_strata.parquet'):
        copy(database, 'SELECT publication_year, work_type, count(*) AS work_count, count(*) FILTER(WHERE is_retracted) AS retracted_count FROM cohort WHERE in_oa GROUP BY ALL', output / 'global_strata.parquet')
    for taxonomy in ['topics_field', 'topics_subfield', 'concepts_l0', 'concepts_l1']:
        print('Baseline strata ' + taxonomy, flush=True)
        target = destination / (taxonomy + '-baseline.parquet')
        if not validate_cache(target):
            copy(database, f'''WITH members AS NOT MATERIALIZED ({membership_sql(taxonomy)}), populations AS (
              SELECT * REPLACE(false AS in_rw) FROM members WHERE in_oa AND subject_id IS NOT NULL
              UNION ALL SELECT * REPLACE(false AS in_oa, rw_subject_id AS subject_id) FROM members WHERE in_rw AND rw_subject_id IS NOT NULL)
              SELECT {literal(taxonomy)} AS taxonomy, subject_id, publication_year, work_type,
                count(*) FILTER(WHERE in_oa) AS work_count, count(*) FILTER(WHERE in_oa AND is_retracted) AS retracted_count,
                count(*) FILTER(WHERE in_rw) AS rw_count FROM populations GROUP BY ALL''', target)
    database.close()


def aggregate(output):
    baseline(output)
    database = connection()
    destination = output / 'aggregates'
    cohort_view(database, output, output / 'cohort.parquet')
    database.execute(f"CREATE VIEW scalar AS SELECT * FROM read_parquet({literal(output / 'scalar/part-*.parquet')})")
    print('Join eligible scalar metrics to study cohorts', flush=True)
    joined = output / 'cohort_metrics.parquet'
    if not validate_cache(joined):
        copy(database, 'SELECT cohort.*, scalar.* EXCLUDE(work_id) FROM cohort JOIN scalar USING(work_id)', joined)
    database.execute(f"CREATE OR REPLACE VIEW cohort AS SELECT * FROM read_parquet({literal(joined)})")
    for taxonomy in ['topics_field', 'topics_subfield', 'concepts_l0', 'concepts_l1']:
        for variant in VARIANTS:
            name = variant[0]
            target = destination / f'{taxonomy}-{name}.parquet'
            if validate_cache(target):
                continue
            print(f'Aggregate {taxonomy}/{name}', flush=True)
            expression = variant_expression(variant)
            short, window = variant[1:3]
            pre = 'false' if window == 'lifetime' else f"try_cast(end_{short}_{window} AS DATE) < retraction_date AND publication_after_retraction IS NOT TRUE"
            query = f'''WITH members AS ({membership_sql(taxonomy)}),
              scored AS (SELECT subject_id, rw_subject_id, in_oa, in_rw, is_retracted,
                {expression} AS score, ({pre}) AS pre_eligible FROM members),
              groups AS (
                SELECT *, 'oa_all' AS population FROM scored WHERE in_oa AND subject_id IS NOT NULL
                UNION ALL SELECT *, 'oa_retracted' FROM scored WHERE in_oa AND is_retracted AND subject_id IS NOT NULL
                UNION ALL SELECT *, 'oa_not_marked' FROM scored WHERE in_oa AND NOT is_retracted AND subject_id IS NOT NULL
                UNION ALL SELECT * REPLACE(rw_subject_id AS subject_id), 'rw' FROM scored WHERE in_rw AND rw_subject_id IS NOT NULL
                UNION ALL SELECT * REPLACE(rw_subject_id AS subject_id), 'rw_pre_retraction' FROM scored WHERE in_rw AND rw_subject_id IS NOT NULL AND pre_eligible
              )
              SELECT {literal(taxonomy)} AS taxonomy, subject_id, {literal(name)} AS variant, population,
                count(score) AS qualified_count, avg(score) AS mean_cd,
                quantile_cont(score, 0.5) AS median_cd, quantile_cont(score, 0.25) AS q25_cd,
                quantile_cont(score, 0.75) AS q75_cd,
                count(*) FILTER(WHERE score > 0)::DOUBLE / nullif(count(score),0) AS positive_fraction
              FROM groups GROUP BY subject_id, population'''
            copy(database, query, target)
        stratified = destination / f'{taxonomy}-main-strata.parquet'
        if not validate_cache(stratified):
            expression = variant_expression(VARIANTS[0])
            copy(database, f'''WITH scored AS (SELECT subject_id, publication_year, work_type, in_oa, is_retracted, {expression} AS score FROM ({membership_sql(taxonomy)}))
              SELECT {literal(taxonomy)} AS taxonomy, subject_id, publication_year, work_type,
                count(score) FILTER(WHERE in_oa) AS qualified_count,
                avg(score) FILTER(WHERE in_oa) AS mean_cd,
                count(score) FILTER(WHERE in_oa AND is_retracted) AS retracted_qualified_count,
                avg(score) FILTER(WHERE in_oa AND is_retracted) AS retracted_mean_cd,
                count(score) FILTER(WHERE in_oa AND NOT is_retracted) AS not_marked_qualified_count,
                avg(score) FILTER(WHERE in_oa AND NOT is_retracted) AS not_marked_mean_cd
              FROM scored WHERE subject_id IS NOT NULL GROUP BY ALL''', stratified)
    files = sorted(destination.glob('*.parquet'))
    write_json(output / 'disruption_manifest.json', {'status': 'complete', 'source_run': str(RUN), 'variants': VARIANTS, 'files': [{'path': str(path), 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in files], 'code_sha256': CODE_SHA256,
        'provenance': {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in ['disruption_config.json', 'cohort.json', 'scalar.json', 'rw_topic_label_audit.json'] if (output / name).exists()}})
    database.close()


def verify_baselines(output):
    published = json.loads(PUBLISHED_FIELDS.read_text())
    explorer = published['discipline_explorer']
    if explorer.get('encoding') == 'zlib-json-v1':
        decoded = zlib.decompress(base64.b64decode(explorer['data']))
        if hashlib.sha256(decoded).hexdigest() != explorer['sha256'] or len(decoded) != explorer['bytes']:
            raise ValueError('Published explorer payload integrity failed')
        explorer = json.loads(decoded)
    taxonomies = {entry['id']: entry for entry in explorer['taxonomies']}
    database = connection(4, '16GB')
    counts = {}
    for taxonomy, system, level in [('concepts_l0', 'concepts', 0), ('concepts_l1', 'concepts', 1), ('topics_field', 'topics', 1), ('topics_subfield', 'topics', 2)]:
        path = output / 'aggregates' / f'{taxonomy}-baseline.parquet'
        actual = {row[0]: row[1:] for row in database.execute(f'SELECT subject_id,sum(work_count),sum(retracted_count) FROM read_parquet({literal(path)}) GROUP BY subject_id').fetchall()}
        expected = {node['id']: (sum(node['denominator'][1:27]), sum(node['counts']['A1'][1:27])) for node in taxonomies[system]['nodes'] if node['level'] == level and not node.get('missing') and not node.get('navigation_only')}
        differences = {identifier: {'actual': actual.get(identifier, (0, 0)), 'expected': pair} for identifier, pair in expected.items() if actual.get(identifier, (0, 0)) != pair}
        unexpected = set(actual) - set(expected)
        if differences or unexpected:
            raise ValueError(f'Published baseline mismatch {taxonomy}: {differences}; extra={unexpected}')
        counts[taxonomy] = len(expected)
    write_json(output / 'baseline_verification.json', {'status': 'passed', 'classified_nodes_verified': counts, 'published_fields_sha256': hashlib.sha256(PUBLISHED_FIELDS.read_bytes()).hexdigest(), 'comparison': 'All classified non-navigation nodes, OA publication years 2000-2025, exact numerator and denominator'})
    database.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['cohort', 'rw_labels', 'baseline', 'scalar', 'aggregate', 'all'], default='all')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    initialize_run(args.output)
    for name, action in [('cohort', cohort), ('rw_labels', rw_labels), ('baseline', baseline), ('scalar', scalar), ('aggregate', aggregate)]:
        if args.stage in ['all', name]:
            action(args.output)
            if name == 'baseline':
                verify_baselines(args.output)
    if args.stage in ['all', 'baseline', 'aggregate']:
        verify_baselines(args.output)


if __name__ == '__main__':
    main()
