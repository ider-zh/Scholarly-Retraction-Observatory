import argparse
import collections
import hashlib
import json
import math
import statistics
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

from ngd_analysis import spearman


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def rows(path):
    return pq.read_table(path).to_pylist()


def verify_manifest(path):
    manifest = json.loads(path.read_text())
    assert manifest['status'] == 'complete', path
    for entry in manifest.get('outputs', []) + manifest.get('files', []):
        target = Path(entry['path'])
        if not target.is_absolute():
            target = path.parent / target
        assert digest(target) == entry['sha256'], target
    for entry in manifest.get('sources', []):
        assert digest(entry['path']) == entry['sha256'], entry['path']
    return manifest


def scientific_review(root):
    subjects = {(row['taxonomy'], row['subject_id']): row for row in rows(root / 'ngd-ranked/subjects.parquet')}
    result = {'methods': {'ecological': 'N>=1000 and qualified CD>=100; equal subject-weight Spearman; raw OA publication2000–2025 rate.',
                          'within_subject': 'Marked qualified>=20 and unmarked qualified>=100; mean difference marked minus unmarked.',
                          'adjusted': 'Same within-subject eligibility plus shared-strata marked qualified>=20. Year×type strata with both groups present; weight by marked qualified count; records common coverage.'}, 'taxonomies': {}}
    for taxonomy in ['concepts_l0', 'concepts_l1', 'topics_field', 'topics_subfield']:
        system = taxonomy.split('_')[0]
        metrics_path = root / f'aggregates/{taxonomy}-main_cd5_r10_c5.parquet'
        strata_path = root / f'aggregates/{taxonomy}-main-strata.parquet'
        if not metrics_path.exists() or not strata_path.exists():
            continue
        metrics = rows(metrics_path)
        lookup = {(row['subject_id'], row['population']): row for row in metrics}
        crude = {}
        for row in metrics:
            if row['population'] != 'oa_retracted' or row['qualified_count'] < 20:
                continue
            other = lookup.get((row['subject_id'], 'oa_not_marked'))
            if other and other['qualified_count'] >= 100:
                crude[row['subject_id']] = row['mean_cd'] - other['mean_cd']
        adjusted = collections.defaultdict(lambda: [0, 0, 0.0])
        for row in rows(strata_path):
            values = adjusted[row['subject_id']]
            values[0] += row['retracted_qualified_count']
            if row['retracted_qualified_count'] and row['not_marked_qualified_count']:
                values[1] += row['retracted_qualified_count']
                values[2] += row['retracted_qualified_count'] * (row['retracted_mean_cd'] - row['not_marked_mean_cd'])
        adjusted_differences = {identifier: values[2] / values[1] for identifier, values in adjusted.items() if identifier in crude and values[1] >= 20}
        variant_stats = []
        for path in sorted((root / 'aggregates').glob(f'{taxonomy}-*.parquet')):
            if path.name.endswith(('-baseline.parquet', '-main-strata.parquet')) or '.partial.' in path.name:
                continue
            qualified = [row for row in rows(path) if row['population'] == 'oa_all' and row['qualified_count'] >= 100 and subjects[system, row['subject_id']]['N'] >= 1000]
            variant_stats.append({'variant': path.name.removeprefix(taxonomy + '-').removesuffix('.parquet'), 'subjects': len(qualified),
                                  'rho': spearman([(row['mean_cd'], subjects[system, row['subject_id']]['rate']) for row in qualified])})
        coverages = [row['qualified_count'] / subjects[system, row['subject_id']]['N'] for row in metrics if row['population'] == 'oa_all' and subjects[system, row['subject_id']]['N'] > 0]
        def summary(values):
            values = list(values)
            return {'subjects': len(values), 'positive': sum(value > 0 for value in values), 'negative': sum(value < 0 for value in values),
                    'zero': sum(value == 0 for value in values), 'median_difference': statistics.median(values) if values else None}
        result['taxonomies'][taxonomy] = {'variants': variant_stats, 'qualification_coverage_median': statistics.median(coverages),
            'crude': summary(crude.values()), 'adjusted': summary(adjusted_differences.values()),
            'adjusted_shared_coverage_median': statistics.median(adjusted[identifier][1] / adjusted[identifier][0] for identifier in adjusted_differences) if adjusted_differences else None,
            'subject_contrasts': [{'subject_id': identifier, 'crude_difference': crude[identifier], 'adjusted_difference': value,
                                  'marked_qualified': adjusted[identifier][0], 'shared_marked_qualified': adjusted[identifier][1]} for identifier, value in adjusted_differences.items()]}
    (root / 'independent_scientific_review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def verify(root, require_complete=False):
    checks = {}
    database = duckdb.connect(config={'threads': 8, 'memory_limit': '16GB'})
    database.read_parquet(str(root / 'cohort.parquet')).create_view('cohort')
    actual = database.execute('''SELECT count(*), count(*) FILTER(WHERE in_oa),
        count(*) FILTER(WHERE in_oa AND is_retracted), count(*) FILTER(WHERE in_rw),
        count(*) FILTER(WHERE work_id IS NULL OR work_id_numeric IS NULL) FROM cohort''').fetchone()
    assert actual == (220306407, 220305891, 77414, 58345, 0), actual
    database.close()
    checks['actual_cohort_rows_and_flags'] = list(actual)
    ngd = root / 'ngd-ranked'
    verify_manifest(ngd / 'manifest.json')
    controls = root / 'ngd-controls-final'
    verify_manifest(controls / 'manifest.json')
    subjects = {(row['taxonomy'], row['subject_id']): row for row in rows(ngd / 'subjects.parquet')}
    baseline = {}
    for taxonomy, system in [('concepts_l0', 'concepts'), ('concepts_l1', 'concepts'), ('topics_field', 'topics'), ('topics_subfield', 'topics')]:
        values = collections.defaultdict(lambda: [0, 0, 0])
        for row in rows(root / f'aggregates/{taxonomy}-baseline.parquet'):
            for index, key in enumerate(['work_count', 'retracted_count', 'rw_count']):
                values[row['subject_id']][index] += row[key]
            assert 0 <= row['retracted_count'] <= row['work_count']
        for identifier, counts in values.items():
            expected = subjects[system, identifier]
            assert counts[:2] == [expected['N'], expected['n']], identifier
            if expected['rw_event_count'] is not None:
                assert counts[2] == expected['rw_event_count'], identifier
            baseline[taxonomy, identifier] = counts
    assert len(baseline) == 581
    checks['independent_baseline_equalities'] = len(baseline)
    manifest = json.loads((ngd / 'manifest.json').read_text())
    originals = {}
    for entry in manifest['sources']:
        if entry['path'].endswith('_l0_l1_ngd.parquet'):
            for row in rows(entry['path']):
                originals[row['taxonomy'], row['l1_id'], row['l0_id']] = row
    comparisons = rows(ngd / 'comparisons.parquet')
    for row in comparisons:
        original = originals[row['taxonomy'], row['subject_id'], row['reference_id']]
        assert row['ngd'] == original['ngd'] and row['ngd_N'] == original['N']
        assert row['ngd_joint'] == original['f_joint'] and row['ngd_status'] == original['ngd_status']
        expected = subjects[row['taxonomy'], row['subject_id']]
        assert row['n'] == expected['n'] and row['N'] == expected['N']
        assert row['rate'] == row['n'] / row['N']
        assert row['parent_id'] in expected['parents']
        assert row['low_events'] == (row['n'] < 20)
        assert row['eligible_ranking'] == (row['N'] >= 1000)
    checks['original_ngd_exact_pairs'] = len(comparisons)
    strict_rows = rows(controls / 'concepts_parent_intersection.parquet')
    assert len(strict_rows) == sum(row['taxonomy'] == 'concepts' for row in comparisons)
    for row in strict_rows:
        assert 0 <= row['intersection_n'] <= row['intersection_N'] <= row['child_only_N']
        assert row['intersection_n'] <= row['child_only_n']
        expected_rate = row['intersection_n'] / row['intersection_N'] if row['intersection_N'] else None
        assert row['intersection_rate'] == expected_rate
    checks['strict_parent_intersections'] = len(strict_rows)
    pending = []
    global_path = root / 'global_main_metrics.json'
    if global_path.exists():
        global_metrics = json.loads(global_path.read_text())
        assert digest(global_metrics['source']) == global_metrics['source_sha256']
        assert Path(global_metrics['source']).stat().st_size == global_metrics['source_bytes']
        lookup = {row['population']: row for row in global_metrics['metrics']}
        limits = {'oa_all': 220305891, 'oa_retracted': 77414, 'oa_not_marked': 220305891 - 77414, 'rw': 58345, 'rw_pre_retraction': 58345}
        assert set(lookup) == set(limits)
        for population, row in lookup.items():
            assert 0 <= row['qualified_count'] <= limits[population]
            assert -1 <= row['mean_cd'] <= 1
            assert -1 <= row['q25_cd'] <= row['median_cd'] <= row['q75_cd'] <= 1
            assert 0 <= row['positive_fraction'] <= 1
        assert lookup['oa_all']['qualified_count'] == lookup['oa_retracted']['qualified_count'] + lookup['oa_not_marked']['qualified_count']
        assert lookup['rw_pre_retraction']['qualified_count'] <= lookup['rw']['qualified_count']
        expected_mean = sum(lookup[population]['qualified_count'] * lookup[population]['mean_cd'] for population in ['oa_retracted', 'oa_not_marked']) / lookup['oa_all']['qualified_count']
        assert math.isclose(expected_mean, lookup['oa_all']['mean_cd'], abs_tol=1e-12)
        checks['global_main_metrics'] = {population: row['qualified_count'] for population, row in lookup.items()}
    else:
        pending.append('global_main_metrics.json')
    cd_manifest = root / 'disruption_manifest.json'
    if cd_manifest.exists():
        manifest = verify_manifest(cd_manifest)
        checked = 0
        for entry in manifest['files']:
            if entry['path'].endswith('-baseline.parquet') or entry['path'].endswith('-main-strata.parquet'):
                continue
            records = rows(entry['path'])
            lookup = {(row['subject_id'], row['population']): row for row in records}
            for row in records:
                counts = baseline[row['taxonomy'], row['subject_id']]
                limit = {'oa_all': counts[0], 'oa_retracted': counts[1], 'oa_not_marked': counts[0] - counts[1], 'rw': counts[2], 'rw_pre_retraction': counts[2]}[row['population']]
                assert 0 <= row['qualified_count'] <= limit
                for key in ['mean_cd', 'median_cd', 'q25_cd', 'q75_cd']:
                    assert row[key] is None or -1 <= row[key] <= 1
                    assert (row[key] is None) == (row['qualified_count'] == 0)
                assert row['positive_fraction'] is None or 0 <= row['positive_fraction'] <= 1
                if row['qualified_count']:
                    assert row['q25_cd'] <= row['median_cd'] <= row['q75_cd']
                if row['population'] == 'oa_all':
                    marked = lookup.get((row['subject_id'], 'oa_retracted'), {'qualified_count': 0})
                    other = lookup.get((row['subject_id'], 'oa_not_marked'), {'qualified_count': 0})
                    assert row['qualified_count'] == marked['qualified_count'] + other['qualified_count']
                    if row['qualified_count']:
                        weighted_sum = sum(group['qualified_count'] * group['mean_cd'] for group in [marked, other] if group['qualified_count'])
                        assert math.isclose(row['mean_cd'], weighted_sum / row['qualified_count'], abs_tol=1e-12)
                checked += 1
        checks['cd_summary_rows'] = checked
    else:
        pending.append('disruption_manifest.json')
    payload_path = root / 'presentation.json'
    if payload_path.exists():
        payload = json.loads(payload_path.read_text())
        for entry in payload['source_manifests'] + payload.get('source_evidence', []):
            assert digest(entry['path']) == entry['sha256']
        scatter = next(slide for slide in payload['slides'] if slide['title'] == '放到所有子学科中，关系并不整齐')
        displayed = collections.Counter((point['x'], point['y']) for series in scatter['chart']['series'] for point in series['points'])
        unique = {(row['taxonomy'], row['subject_id']): row for row in comparisons if row['reference'] == 'Mathematics' and row['eligible_ranking']}
        expected = collections.Counter((row['ngd'], row['rate'] * 100) for row in unique.values())
        assert displayed == expected
        checks['ppt_math_scatter_points_exact'] = sum(displayed.values())
    else:
        pending.append('presentation.json')
    if require_complete:
        assert not pending, pending
    return {'status': 'passed' if not pending else 'partial_pass_pending_stages', 'checks': checks, 'pending': pending,
            'scope': 'Full source/aggregate checksums, actual cohort flag counts, all baseline equalities, every NGD comparison, CD summary invariants when complete, mathematical scatter payload values. Does not independently recompute all CD graph counts or assess slide rendering.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    result = verify(args.root, args.require_complete)
    scientific_review(args.root)
    destination = args.root / ('independent_crossstudy_verification.json' if args.require_complete else 'independent_crossstudy_partial.json')
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False))
