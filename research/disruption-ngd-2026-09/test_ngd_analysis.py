import importlib.util
from pathlib import Path
import unittest
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq


SPEC = importlib.util.spec_from_file_location('ngd_analysis', Path(__file__).with_name('ngd_analysis.py'))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class StatisticsTests(unittest.TestCase):
    def test_spearman_ties_and_missing(self):
        self.assertAlmostEqual(MODULE.spearman([(1, 2), (1, 2), (3, 4), (None, 0)]), 1)
        self.assertIsNone(MODULE.spearman([(1, 2), (1, 4), (1, 6)]))
        self.assertIsNone(MODULE.spearman([(1, 2), (3, 4)]))

    def test_ties_never_split(self):
        rows = MODULE.distance_groups([{'ngd': value} for value in [1, 1, 1, 1, 2, 3, None]])
        self.assertEqual(len({row['distance_group'] for row in rows if row['ngd'] == 1}), 1)
        self.assertIsNone(rows[-1]['distance_group'])

    def test_zero_not_zero_risk(self):
        lower, upper = MODULE.wilson(0, 1000)
        self.assertAlmostEqual(lower, 0)
        self.assertGreater(upper, 0)
        self.assertEqual(MODULE.wilson(0, 0), (None, None))

    def test_empty_distance(self):
        self.assertIsNone(MODULE.distance_groups([{'ngd': None}])[0]['distance_group'])

    def test_controls_and_parent_intersection(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            cohort, ngd, initial = [base / name for name in ['cohort', 'ngd', 'initial']]
            for directory in [cohort / 'aggregates', ngd, initial]:
                directory.mkdir(parents=True)
            (initial / 'manifest.json').write_text('{"status":"complete"}')
            strata = [{'publication_year': 2000, 'work_type': 'article', 'work_count': 2, 'retracted_count': 1},
                      {'publication_year': 2001, 'work_type': 'article', 'work_count': 1, 'retracted_count': 0}]
            pq.write_table(pa.Table.from_pylist(strata), cohort / 'global_strata.parquet')
            pq.write_table(pa.Table.from_pylist([{**row, 'taxonomy': 'concepts_l1', 'subject_id': 'child'} for row in strata]), cohort / 'aggregates/concepts_l1-baseline.parquet')
            pq.write_table(pa.Table.from_pylist([{'taxonomy': 'concepts', 'subject_id': 'child', 'N': 3, 'n': 1}]), initial / 'subjects.parquet')
            comparison = {'taxonomy': 'concepts', 'subject_id': 'child', 'N': 3, 'n': 1, 'eligible_ranking': True,
                          'reference': 'Mathematics', 'parent_id': 'parent', 'parent_name': 'Parent', 'parent_is_high_rate': True, 'ngd': .5}
            pq.write_table(pa.Table.from_pylist([comparison]), initial / 'comparisons.parquet')
            pq.write_table(pa.Table.from_pylist([{'taxonomy': 'concepts', 'l0_id': 'parent', 'l1_id': 'child'}]), ngd / 'taxonomy_parent_edges.parquet')
            papers = [{'in_oa': True, 'is_retracted': index == 0, 'concept_l0_ids': ['parent'] if index < 2 else [], 'concept_l1_ids': ['child']} for index in range(3)]
            pq.write_table(pa.Table.from_pylist(papers), cohort / 'cohort.parquet')
            MODULE.controls(cohort, ngd, initial, base / 'output')
            result = pq.read_table(base / 'output/year_type_controls.parquet').to_pylist()[0]
            self.assertAlmostEqual(result['indirect_year_type_rate'], 1 / 3)
            self.assertAlmostEqual(result['direct_year_type_rate'], 1 / 3)
            result = pq.read_table(base / 'output/concepts_parent_intersection.parquet').to_pylist()[0]
            self.assertEqual((result['intersection_N'], result['intersection_n']), (2, 1))
            self.assertEqual((result['child_only_N'], result['child_only_n']), (3, 1))


if __name__ == '__main__':
    unittest.main()
