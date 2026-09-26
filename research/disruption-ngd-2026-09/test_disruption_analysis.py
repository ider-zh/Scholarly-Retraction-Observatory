import importlib.util
from pathlib import Path
import unittest
import tempfile

import duckdb


spec = importlib.util.spec_from_file_location('disruption_analysis', Path(__file__).with_name('disruption_analysis.py'))
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
global_spec = importlib.util.spec_from_file_location('global_metrics', Path(__file__).with_name('export_global_metrics.py'))
global_metrics = importlib.util.module_from_spec(global_spec)
global_spec.loader.exec_module(global_metrics)


class DisruptionAnalysisTest(unittest.TestCase):
    def test_main_thresholds_and_null(self):
        database = duckdb.connect()
        database.execute('CREATE TABLE cases(reference_count INTEGER, citations_ex_5y INTEGER, mature_ex_5y BOOLEAN, cd_ex_5y DOUBLE)')
        database.execute('INSERT INTO cases VALUES (10,5,true,.2),(9,5,true,.2),(10,4,true,.2),(10,5,false,.2),(10,5,true,NULL),(10,5,NULL,.2)')
        rows = database.execute('SELECT ' + analysis.variant_expression(analysis.VARIANTS[0]) + ' FROM cases').fetchall()
        self.assertEqual(rows, [(0.2,), (None,), (None,), (None,), (None,), (None,)])

    def test_lifetime_not_excluded_for_missing_maturity(self):
        database = duckdb.connect()
        database.execute('CREATE TABLE cases(reference_count INTEGER, citations_ex_lifetime INTEGER, cd_ex_lifetime DOUBLE)')
        database.execute('INSERT INTO cases VALUES(10,5,-.3)')
        variant = next(item for item in analysis.VARIANTS if item[0] == 'cd_lifetime_r10_c5')
        self.assertEqual(database.execute('SELECT ' + analysis.variant_expression(variant) + ' FROM cases').fetchone(), (-.3,))

    def test_concept_duplicates_and_primary_only(self):
        database = duckdb.connect()
        database.execute("CREATE TABLE cohort AS SELECT ['C1','C1','C2'] concept_l0_ids, 'F1' field_id, 'F1' rw_field_id")
        self.assertEqual(sorted(row[-1] for row in database.execute(analysis.membership_sql('concepts_l0')).fetchall()), ['C1', 'C2'])
        self.assertEqual(database.execute(analysis.membership_sql('topics_field')).fetchone()[-1], 'F1')

    def test_zero_reference_no_extra_not_qualified(self):
        database = duckdb.connect()
        database.execute('CREATE TABLE cases(reference_count INTEGER, citations_ex_5y INTEGER, mature_ex_5y BOOLEAN, cd_ex_5y DOUBLE)')
        database.execute('INSERT INTO cases VALUES(0,10,true,1),(1,0,true,-1)')
        result = database.execute('SELECT ' + analysis.variant_expression(analysis.VARIANTS[1]) + ' FROM cases').fetchall()
        self.assertEqual(result, [(None,), (-1.0,)])

    def test_aggregate_preserves_baseline_and_rw_population(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            database = duckdb.connect()
            database.execute("""CREATE TABLE cohort AS SELECT 'W1' work_id, 2010 publication_year,
              'article' work_type, true is_retracted, true in_oa, true in_rw,
              'F1' field_id, 'S1' subfield_id, ['C0'] concept_l0_ids, ['C1'] concept_l1_ids,
              DATE '2020-01-01' retraction_date, false publication_after_retraction, DATE '2010-01-01' publication_date
              UNION ALL SELECT 'W2',2010,'article',false,true,false,'F1','S1',['C0'],['C1'],NULL,NULL,NULL""")
            analysis.copy(database, 'SELECT * FROM cohort', output / 'cohort.parquet')
            analysis.copy(database, "SELECT work_id, 'F2' AS rw_field_id, 'S2' AS rw_subfield_id FROM cohort WHERE in_rw", output / 'rw_topic_labels.parquet')
            expressions = ["'W1' AS work_id", '10 AS reference_count']
            for short, _ in analysis.POLICIES:
                for window in ['3y', '5y', '10y', 'lifetime']:
                    expressions.extend([f'.2 AS cd_{short}_{window}', f'.5 AS no_nr_{short}_{window}',
                                        f'5 AS citations_{short}_{window}', f'true AS mature_{short}_{window}',
                                        f"'2015-12-31' AS end_{short}_{window}"])
            (output / 'scalar').mkdir()
            analysis.copy(database, 'SELECT ' + ','.join(expressions), output / 'scalar/part-000000.parquet')
            analysis.aggregate(output)
            baseline = database.execute(f"SELECT sum(work_count),sum(retracted_count) FROM read_parquet('{output}/aggregates/topics_field-baseline.parquet')").fetchone()
            self.assertEqual(baseline, (2, 1))
            stats = dict(database.execute(f"SELECT population,qualified_count FROM read_parquet('{output}/aggregates/topics_field-main_cd5_r10_c5.parquet')").fetchall())
            self.assertEqual(stats['oa_all'], 1)
            self.assertEqual(stats['rw_pre_retraction'], 1)
            rw_subject = database.execute(f"SELECT subject_id FROM read_parquet('{output}/aggregates/topics_field-main_cd5_r10_c5.parquet') WHERE population='rw'").fetchone()[0]
            self.assertEqual(rw_subject, 'F2')

    def test_global_export_replay_preserves_cache_and_rejects_source_change(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            database = duckdb.connect()
            query = """SELECT true in_oa,true in_rw,true is_retracted,
              '2015-12-31' end_ex_5y,DATE '2020-01-01' retraction_date,
              false publication_after_retraction,10 reference_count,5 citations_ex_5y,
              true mature_ex_5y,.2 cd_ex_5y
              UNION ALL SELECT true,false,false,'2015-12-31',NULL,false,0,0,true,NULL"""
            analysis.copy(database, query, output / 'cohort_metrics.parquet')
            global_metrics.export(output)
            original = (output / 'global_main_metrics.json').read_bytes()
            global_metrics.export(output)
            self.assertEqual(original, (output / 'global_main_metrics.json').read_bytes())
            analysis.copy(database, query.replace('.2 cd_ex_5y', '.3 cd_ex_5y'), output / 'cohort_metrics.parquet')
            with self.assertRaises(ValueError):
                global_metrics.export(output)


if __name__ == '__main__':
    unittest.main()
