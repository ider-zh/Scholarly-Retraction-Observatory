import argparse
import collections
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics

import pyarrow as pa
import pyarrow.parquet as pq


REFERENCES = {
    'concepts': {'Mathematics': 'C33923547', 'Computer science': 'C41008148', 'Physics': 'C121332964'},
    'topics': {'Mathematics': 'fields/26', 'Computer science': 'fields/17', 'Physics': 'fields/31'},
}


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def ranks(values):
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    result = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][1] == ordered[start][1]:
            end += 1
        for index, _ in ordered[start:end]:
            result[index] = (start + end - 1) / 2 + 1
        start = end
    return result


def spearman(pairs):
    pairs = [(first, second) for first, second in pairs if first is not None and second is not None]
    if len(pairs) < 3:
        return None
    first, second = zip(*pairs)
    first, second = ranks(first), ranks(second)
    if len(set(first)) < 2 or len(set(second)) < 2:
        return None
    return statistics.correlation(first, second)


def wilson(events, total):
    if not total:
        return None, None
    estimate = events / total
    denominator = 1 + 1.96 ** 2 / total
    center = (estimate + 1.96 ** 2 / (2 * total)) / denominator
    radius = 1.96 * math.sqrt(estimate * (1 - estimate) / total + 1.96 ** 2 / (4 * total ** 2)) / denominator
    return max(0, center - radius), min(1, center + radius)


def distance_groups(rows):
    values = [row['ngd'] for row in rows if row['ngd'] is not None]
    dense_ranks = {value: index + 1 for index, value in enumerate(sorted(set(values)))}
    low, high = percentile(values, 1 / 3), percentile(values, 2 / 3)
    for row in rows:
        value = row['ngd']
        row['distance_group'] = None if value is None else ('near' if value <= low else 'middle' if value <= high else 'far')
        row['distance_cut_low'], row['distance_cut_high'] = low, high
        row['distance_rank_within_parent'] = dense_ranks.get(value)
    return rows


def write_table(directory, name, rows):
    pq.write_table(pa.Table.from_pylist(rows), directory / f'{name}.parquet', compression='zstd')
    with gzip.open(directory / f'{name}.json.gz', 'wt', encoding='utf-8') as handle:
        json.dump(rows, handle, ensure_ascii=False, allow_nan=False)
    with gzip.open(directory / f'{name}.csv.gz', 'wt', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in row.items()})


def analyze(published, ngd_directory, rw):
    subjects, annual, comparisons, summaries = [], [], [], []
    coverage = {}
    for taxonomy in published['fields']['discipline_explorer']['taxonomies']:
        system = taxonomy['id']
        if system not in REFERENCES:
            continue
        total = sum(taxonomy['denominator'][1:27])
        assert total == 220305891 and sum(taxonomy['counts']['A1'][1:27]) == 77414
        weights = [count / total for count in taxonomy['denominator'][1:27]]
        base_level = 0 if system == 'concepts' else 1
        rw_groups = ['concepts_l0', 'concepts_l1'] if system == 'concepts' else ['topics_field', 'topics_subfield']
        rw_lookup = {node['id']: node['total'] for group in rw_groups for node in rw['groups'][group]['nodes']}
        lookup = {}
        for node in taxonomy['nodes']:
            if node['level'] not in (base_level, base_level + 1) or node.get('missing'):
                continue
            counts, denominators = node['counts']['A1'][1:27], node['denominator'][1:27]
            events, population = sum(counts), sum(denominators)
            assert 0 <= events <= population
            coverage_weight = sum(weight for weight, denominator in zip(weights, denominators) if denominator)
            standardized = sum(weight * count / denominator for weight, count, denominator in zip(weights, counts, denominators) if denominator)
            lower, upper = wilson(events, population)
            row = {'taxonomy': system, 'subject_id': node['id'], 'name': node['label'], 'level': node['level'] - base_level,
                   'parents': node['parents'], 'N': population, 'n': events, 'rate': events / population if population else None,
                   'wilson_lower': lower, 'wilson_upper': upper, 'low_events': events < 20, 'eligible_ranking': population >= 1000,
                   'year_standardized_rate': standardized if coverage_weight >= 1 - 1e-12 else None,
                   'year_weight_coverage': coverage_weight, 'rw_event_count': rw_lookup.get(node['id']), 'rw_event_total': 58345}
            subjects.append(row)
            lookup[node['id']] = row
            annual.extend({'taxonomy': system, 'subject_id': node['id'], 'year': 2000 + index, 'N': denominator, 'n': count,
                           'rate': count / denominator if denominator else None} for index, (count, denominator) in enumerate(zip(counts, denominators)))
        high_cut = percentile([row['rate'] for row in lookup.values() if row['level'] == 0 and row['eligible_ranking']], .75)
        for row in lookup.values():
            row['parent_high_rate_cutoff'] = high_cut
            row['high_rate_parent'] = row['level'] == 0 and row['eligible_ranking'] and row['rate'] >= high_cut
        matrix = pq.read_table(ngd_directory / f'{system}_l0_l1_ngd.parquet').to_pylist()
        distance_lookup = {(row['l1_id'], row['l0_id']): row for row in matrix}
        coverage[system] = {'child_nodes': sum(row['level'] == 1 for row in lookup.values()), 'missing_pairs': []}
        for reference, identifier in REFERENCES[system].items():
            reference_id = f'https://openalex.org/{identifier}'
            all_rows = []
            for child in lookup.values():
                if child['level'] != 1:
                    continue
                pair = distance_lookup.get((child['subject_id'], reference_id))
                if pair is None:
                    coverage[system]['missing_pairs'].append([child['subject_id'], reference_id])
                distance = pair['ngd'] if pair else None
                all_rows.append((distance, child))
                for parent_id in child['parents']:
                    parent = lookup.get(parent_id)
                    if not parent or parent['level'] != 0:
                        continue
                    comparisons.append({**child, 'parent_id': parent_id, 'parent_name': parent['name'], 'parent_rate': parent['rate'],
                                        'parent_is_high_rate': parent['high_rate_parent'], 'reference': reference, 'reference_id': reference_id,
                                        'ngd': distance, 'ngd_status': pair['ngd_status'] if pair else 'missing_pair',
                                        'ngd_N': pair['N'] if pair else None, 'ngd_joint': pair['f_joint'] if pair else None})
            eligible = [(distance, child) for distance, child in all_rows if child['eligible_ranking']]
            summaries.append({'taxonomy': system, 'reference': reference, 'scope': 'all_unique_children', 'parent_id': None, 'parent_name': None,
                              'parent_is_high_rate': None, 'children': len(eligible), 'defined_distance_children': sum(distance is not None for distance, _ in eligible),
                              'spearman_crude': spearman([(distance, child['rate']) for distance, child in eligible]),
                              'spearman_year_standardized': spearman([(distance, child['year_standardized_rate']) for distance, child in eligible])})
    grouped = collections.defaultdict(list)
    for row in comparisons:
        grouped[(row['taxonomy'], row['reference'], row['parent_id'])].append(row)
    bands = []
    for (system, reference, parent_id), rows in grouped.items():
        distance_groups(rows)
        eligible = [row for row in rows if row['eligible_ranking']]
        summaries.append({'taxonomy': system, 'reference': reference, 'scope': 'within_parent', 'parent_id': parent_id,
                          'parent_name': rows[0]['parent_name'], 'parent_is_high_rate': rows[0]['parent_is_high_rate'], 'children': len(eligible),
                          'defined_distance_children': sum(row['ngd'] is not None for row in eligible),
                          'spearman_crude': spearman([(row['ngd'], row['rate']) for row in eligible]),
                          'spearman_year_standardized': spearman([(row['ngd'], row['year_standardized_rate']) for row in eligible])})
        for band in ['near', 'middle', 'far']:
            selected = [row for row in eligible if row['distance_group'] == band]
            rates = [row['rate'] for row in selected]
            adjusted = [row['year_standardized_rate'] for row in selected if row['year_standardized_rate'] is not None]
            bands.append({'taxonomy': system, 'reference': reference, 'parent_id': parent_id, 'parent_name': rows[0]['parent_name'],
                          'parent_is_high_rate': rows[0]['parent_is_high_rate'], 'distance_group': band, 'children': len(selected),
                          'median_child_rate': statistics.median(rates) if rates else None,
                          'median_child_year_standardized_rate': statistics.median(adjusted) if adjusted else None,
                          'low_event_children': sum(row['low_events'] for row in selected)})
    return {'subjects': subjects, 'annual': annual, 'comparisons': comparisons, 'correlations': summaries, 'distance_bands': bands}, coverage


def controls(cohort_directory, ngd_directory, initial_directory, output):
    import duckdb

    output.mkdir(parents=True, exist_ok=False)
    database = duckdb.connect(config={'threads': 8, 'memory_limit': '64GB'})
    database.execute('SET temp_directory = ?', [str(output / '_spill')])
    database.execute("SET max_temp_directory_size = '400GB'")
    database.read_parquet(str(cohort_directory / 'global_strata.parquet')).create_view('global_strata')
    database.read_parquet(str(cohort_directory / 'aggregates/*-baseline.parquet')).create_view('strata')
    table = database.execute('''WITH weights AS (
        SELECT publication_year, work_type, work_count, retracted_count, work_count / sum(work_count) OVER() AS weight,
        retracted_count / work_count AS rate, sum(retracted_count) OVER() / sum(work_count) OVER() AS overall_rate FROM global_strata
        WHERE work_count > 0
    ) SELECT taxonomy,subject_id,sum(strata.work_count)::BIGINT AS work_count,sum(strata.retracted_count)::BIGINT AS retracted_count,
        sum(strata.work_count * weights.rate) AS expected_n,
        sum(strata.retracted_count) / nullif(sum(strata.work_count * weights.rate),0) AS observed_expected_ratio,
        sum(strata.retracted_count) / nullif(sum(strata.work_count * weights.rate),0) * max(overall_rate) AS indirect_year_type_rate,
        sum(weight) FILTER(WHERE strata.work_count > 0) AS direct_weight_coverage,
        CASE WHEN sum(weight) FILTER(WHERE strata.work_count > 0) >= 1-1e-12
            THEN sum(weight * strata.retracted_count / nullif(strata.work_count,0)) ELSE NULL END AS direct_year_type_rate
        FROM strata JOIN weights ON strata.publication_year=weights.publication_year
          AND strata.work_type IS NOT DISTINCT FROM weights.work_type
        GROUP BY taxonomy,subject_id''').fetch_arrow_table()
    rows = table.to_pylist()
    for row in rows:
        row['N'], row['n'] = row['work_count'], row['retracted_count']
        row['taxonomy_level'] = row['taxonomy']
        row['taxonomy'] = 'concepts' if row['taxonomy'].startswith('concepts') else 'topics'
    write_table(output, 'year_type_controls', rows)
    lookup = {(row['taxonomy'], row['subject_id']): row for row in rows}
    original = pq.read_table(initial_directory / 'subjects.parquet').to_pylist()
    for row in original:
        if (row['taxonomy'], row['subject_id']) not in lookup and row['N'] == 0 and row['n'] == 0:
            continue
        controlled = lookup[(row['taxonomy'], row['subject_id'])]
        assert (row['N'], row['n']) == (controlled['N'], controlled['n']), row['subject_id']
    comparisons = pq.read_table(initial_directory / 'comparisons.parquet').to_pylist()
    for row in comparisons:
        row.update({key: lookup[(row['taxonomy'], row['subject_id'])][key] for key in ['indirect_year_type_rate', 'observed_expected_ratio', 'direct_year_type_rate', 'direct_weight_coverage']})
    write_table(output, 'comparisons_controlled', comparisons)
    grouped = collections.defaultdict(dict)
    for row in comparisons:
        if row['eligible_ranking']:
            grouped[(row['taxonomy'], row['reference'], row['parent_id'])][row['subject_id']] = row
            grouped[(row['taxonomy'], row['reference'], None)][row['subject_id']] = row
    correlations = []
    for (taxonomy, reference, parent_id), members in grouped.items():
        values = list(members.values())
        correlations.append({'taxonomy': taxonomy, 'reference': reference, 'parent_id': parent_id,
                             'parent_name': values[0]['parent_name'] if parent_id else None,
                             'parent_is_high_rate': values[0]['parent_is_high_rate'] if parent_id else None,
                             'children': len(values), 'spearman_indirect_year_type': spearman([(row['ngd'], row['indirect_year_type_rate']) for row in values])})
    write_table(output, 'correlations_controlled', correlations)
    database.read_parquet(str(cohort_directory / 'cohort.parquet')).create_view('cohort')
    database.read_parquet(str(ngd_directory / 'taxonomy_parent_edges.parquet')).create_view('edges')
    intersection = database.execute('''SELECT edges.l0_id AS parent_id, edges.l1_id AS subject_id,
       count(*)::BIGINT AS work_count,count(*) FILTER(WHERE is_retracted)::BIGINT AS retracted_count
       FROM (SELECT is_retracted,concept_l0_ids,unnest(concept_l1_ids) AS subject_id
             FROM cohort WHERE in_oa) attached
       JOIN edges ON edges.taxonomy='concepts' AND edges.l1_id=attached.subject_id
       WHERE list_contains(concept_l0_ids,edges.l0_id) GROUP BY edges.l0_id,edges.l1_id''').fetch_arrow_table().to_pylist()
    intersection_lookup = {(row['parent_id'], row['subject_id']): {'N': row['work_count'], 'n': row['retracted_count']} for row in intersection}
    strict_rows = []
    for row in comparisons:
        if row['taxonomy'] != 'concepts':
            continue
        counts = intersection_lookup.get((row['parent_id'], row['subject_id']), {'N': 0, 'n': 0})
        strict_rows.append({**row, 'child_only_N': row['N'], 'child_only_n': row['n'],
                           'intersection_N': counts['N'], 'intersection_n': counts['n'],
                           'intersection_rate': counts['n'] / counts['N'] if counts['N'] else None,
                           'intersection_coverage': counts['N'] / row['N'] if row['N'] else None})
    write_table(output, 'concepts_parent_intersection', strict_rows)
    database.close()
    sources = [cohort_directory / 'global_strata.parquet', initial_directory / 'manifest.json', ngd_directory / 'taxonomy_parent_edges.parquet'] + sorted((cohort_directory / 'aggregates').glob('*-baseline.parquet'))
    if (cohort_directory / 'cohort.json').exists():
        sources.append(cohort_directory / 'cohort.json')
    manifest = {'status': 'complete', 'initial': str(initial_directory), 'cohort_directory': str(cohort_directory),
                'sources': [{'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in sources],
                'cohort_file': {'path': str(cohort_directory / 'cohort.parquet'), 'bytes': (cohort_directory / 'cohort.parquet').stat().st_size},
                'row_counts': {'controls': len(rows), 'intersection_comparisons': len(strict_rows)},
                'methods': 'Indirect year/type: expected n=sum(subject stratum N × full OA stratum rate), adjusted rate=(observed/expected) × full OA rate. O/E depends on subject stratum weights, not a causal adjustment or common direct standard. Direct rate NULL unless all global positively weighted strata represented. Concepts strict parent-intersection is separate sensitivity, never replaces child-only main denominator.',
                'outputs': [{'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(output.iterdir()) if path.is_file()]}
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps(manifest['row_counts']))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--published', type=Path, default=Path('/tmp/retraction-kdocs-20260916/published.json'))
    parser.add_argument('--rw', type=Path, default=Path('/tmp/retraction-nick-20260920/analysis.json'))
    parser.add_argument('--ngd', type=Path, default=Path('/mnt/hg02/openalex-snapshot/analysis/taxonomy-ngd/46194db71c3b1c538ce87257994318307a066c9708ca9038d8a0d48233ba9319/final'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--controls-cohort', type=Path)
    parser.add_argument('--initial', type=Path)
    arguments = parser.parse_args()
    if arguments.controls_cohort:
        controls(arguments.controls_cohort, arguments.ngd, arguments.initial, arguments.output)
        return
    arguments.output.mkdir(parents=True, exist_ok=False)
    published, rw = json.loads(arguments.published.read_text()), json.loads(arguments.rw.read_text())
    assert rw['summary']['total'] == 58345
    root = Path(__file__).resolve().parents[2]
    for entry in published['manifest']['files']:
        path = root / 'public' / entry['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], path
    tables, coverage = analyze(published, arguments.ngd, rw)
    for level in (0, 1):
        observed = [row for row in tables['subjects'] if row['taxonomy'] == 'topics' and row['level'] == level]
        assert sum(row['N'] for row in observed) <= 220305891
        assert sum(row['n'] for row in observed) <= 77414
    for name, rows in tables.items():
        write_table(arguments.output, name, rows)
    sources = [arguments.published, arguments.rw] + [arguments.ngd / f'{system}_l0_l1_ngd.parquet' for system in REFERENCES]
    manifest = {'status': 'complete', 'coverage': coverage, 'table_rows': {name: len(rows) for name, rows in tables.items()},
                'sources': [{'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in sources],
                'published_source_hashes_checked': len(published['manifest']['files']),
                'outputs': [{'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(arguments.output.iterdir())],
                'methods': {'cohort': 'Existing core broad original_supported/unresolved; OA publication 2000–2025; RW earliest event 2000–2025.',
                            'ngd': 'External all-core+xpac all-tag cooccurrence distance, not text semantic distance. Topics rates primary_topic; NGD all topics.',
                            'year_standardization': 'Direct global OA publication-year weights, NULL if any positively weighted year has zero subject denominator. Not year/type controlled.',
                            'bands': 'Within-parent NGD interpolated terciles over all children; ties remain together, potentially empty groups; summaries median of N>=1000 child rates, no overlapping-concept pooling.',
                            'correlation': 'Unweighted descriptive Spearman over N>=1000 subjects. No p-values/causal claims; correlated overlapping labels.',
                            'uncertainty': 'Wilson descriptive binomial intervals; no claim snapshot sampling or ascertainment uncertainty captured.'}}
    (arguments.output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps({'output': str(arguments.output), 'rows': manifest['table_rows'], 'coverage': coverage}))


if __name__ == '__main__':
    main()
