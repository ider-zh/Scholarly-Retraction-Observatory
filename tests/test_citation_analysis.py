import datetime as dt
from pathlib import Path
import tempfile
import unittest

try:
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
except ModuleNotFoundError as error:
    raise unittest.SkipTest('Install snapshot requirements') from error

from pipeline.citation_analysis import anniversary, classify, date_interval, summarize, windows
from pipeline.snapshot_citations import scan_file
from pipeline.reason_families import families, MAPPING, GROUPS
from pipeline.publisher_analysis import parent_root
from pipeline.extended_descriptive import build_charts, growth
from pipeline.snapshot_report import chart, count_row


def target(identifier, event='2020-02-29'):
    return {'target_id': identifier, 'event_date': event, 'publication_date': '2010-01-01',
            'publication_year': 2010, 'event_date_conflict': False, 'event_after_cutoff': False}


class CitationAnalysisTests(unittest.TestCase):
    def test_coarse_and_same_day_dates_are_ambiguous(self):
        event = date_interval('2020-05-04')
        self.assertEqual(classify(date_interval('2020'), event), 'ambiguous')
        self.assertEqual(classify(date_interval('2020-05'), event), 'ambiguous')
        self.assertEqual(classify(event, event), 'ambiguous')
        self.assertEqual(classify(date_interval('2020-05-03'), event), 'before')
        self.assertEqual(classify(date_interval('2020-05-05'), event), 'after')
        self.assertEqual(classify(None, event), 'undated')
        self.assertIsNone(date_interval('invalid'))

    def test_calendar_windows_and_incomplete_followup(self):
        self.assertEqual(anniversary(dt.date(2020, 2, 29), 1), dt.date(2021, 2, 28))
        annual, fixed = windows(target('old'), dt.date(2023, 2, 27))
        self.assertIn(1, fixed)
        self.assertNotIn(3, fixed)
        self.assertNotIn(5, fixed)
        annual, fixed = windows(target('young', '2025-01-01'), dt.date(2026, 6, 26))
        self.assertEqual(set(fixed), {1})

    def test_distinct_incoming_not_outgoing_references(self):
        with tempfile.TemporaryDirectory() as directory, duckdb.connect() as connection:
            source, output = Path(directory)/'source.parquet', Path(directory)/'edges.parquet'
            pq.write_table(pa.table({'id': ['original', 'citing'], 'referenced_works': [['other'], ['original', 'original']],
                'publication_date': [dt.date(2010, 1, 1), dt.date(2021, 1, 1)], 'publication_year': [2010, 2021],
                'type': ['article', 'article'], 'is_xpac': [False, True]}), source)
            count = scan_file(connection, source, pa.table({'target_id': ['original']}), output)
            self.assertEqual(count, 1)
            edge = pq.read_table(output).to_pylist()[0]
            self.assertEqual(edge['citing_id'], 'citing')
            self.assertTrue(edge['is_xpac'])

    def test_zero_targets_retained_and_temporal_partition(self):
        targets = [target('old'), target('zero'), target('recent', '2025-01-01'), target('missing', None)]
        edges = [{'target_id': 'old', 'publication_date': value, 'publication_year': year, 'type': 'article'}
                 for value, year in [('2019-01-01', 2019), ('2020-02-29', 2020), ('2020-03-01', 2020),
                                     (None, None), (None, 2020), ('2027-01-01', 2027)]]
        result = summarize(targets, [edges], '2026-06-26', {'old': 10, 'zero': 0})
        self.assertEqual(result['states'], {'before': 1, 'ambiguous': 2, 'after': 1, 'undated': 2})
        self.assertEqual(result['coarse_states']['ambiguous'], 3)
        common = [row for row in result['fixed'] if row['cohort_mode'] == 'common_5y']
        self.assertEqual([row['denominator'] for row in common], [2, 2, 2])
        self.assertEqual(common[0]['value'], .5)
        self.assertEqual(common[0]['median'], .5)
        self.assertEqual(common[0]['targets_with_edges_pct'], 50)
        self.assertEqual(common[0]['excluded_targets'], 2)
        self.assertEqual(result['static_audit']['different_targets'], 1)

    def test_all_undated_gives_no_classifiable_denominator(self):
        result = summarize([target('missing', None)], [[{'target_id': 'missing', 'publication_date': None,
            'publication_year': None, 'type': 'article'}]], '2026-06-26')
        self.assertEqual(result['states'], {'undated': 1})
        self.assertTrue(all(row['value'] is None for row in result['fixed']))

    def test_reason_mapping_preserves_procedure_and_unknown(self):
        self.assertEqual(families(['Error in Data', 'Error in Image']), {'reported_error'})
        self.assertEqual(families(['Investigation by ORI']), {'investigation'})
        self.assertEqual(families(['New label']), {'unmapped'})
        self.assertEqual(families([]), {'missing'})
        self.assertNotEqual(MAPPING['Misconduct - Official Investigation(s) and/or Finding(s)'], ['misconduct_label'])
        self.assertEqual(len(MAPPING), sum(len(group[2].split(';')) for group in GROUPS.values()))

    def test_publisher_parent_chain_does_not_guess(self):
        publishers = {'P1': {'parent_publisher': {'id': 'P2'}}, 'P2': {'parent_publisher': None}}
        self.assertEqual(parent_root('P1', publishers), 'P2')
        self.assertIsNone(parent_root('I1', publishers))
        publishers['P2']['parent_publisher'] = {'id': 'P1'}
        self.assertIsNone(parent_root('P1', publishers))

    def test_any_topic_parents_deduplicate_and_partial_month_is_not_flagged(self):
        works = {'W1': {'topics': [{'id': 'T1', 'field': {'id': 'F1', 'display_name': 'Field'}},
                                   {'id': 'T2', 'field': {'id': 'F1', 'display_name': 'Field'}}]}}
        result = build_charts([{'retracted': '2026-09-01'}]*30, works, {'W1'}, {}, '2026-06-26', '2026-09-10', chart, count_row)
        field = next(item for item in result['fields'] if item['slice_id']=='A1-any-topic-field')
        self.assertEqual(field['rows'][0]['numerator'], 1)
        control = result['publishing'][0]
        self.assertEqual(control['rows'][-1]['numerator'], 30)
        self.assertTrue(control['rows'][-1]['partial'])
        self.assertFalse(control['rows'][-1]['review_flag'])
        self.assertIsNone(growth(1, 0))
        self.assertEqual(growth(10, 20), -50)


if __name__ == '__main__':
    unittest.main()
