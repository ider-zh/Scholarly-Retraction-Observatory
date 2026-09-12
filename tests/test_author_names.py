import csv
import tempfile
import unittest
from pathlib import Path

from pipeline.author_names import raw_name_counts, build_chart
from pipeline.snapshot_report import chart, count_row
from pipeline.validate_snapshot import digest


class AuthorNameTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name) / 'rw.csv'
        with self.source.open('w', newline='') as output:
            writer = csv.writer(output)
            writer.writerow(['Record ID', 'Author'])
            writer.writerows([['1', 'Wei Wang; Wei Wang; Unknown'], ['2', 'Wei Wang;Wei Zhang'],
                              ['3', 'Wei Wang; wei wang'], ['4', 'Unknown'], ['5', ''],
                              ['6', 'EXCLUDED AUTHOR'], ['', ''], ['', '']])
        self.sha = digest(self.source.read_bytes())
        self.papers = [{'id': 'first', 'rw_ids': ['1', '2']}, {'id': 'second', 'rw_ids': ['3']},
                       {'id': 'missing', 'rw_ids': ['4']}, {'id': 'blank', 'rw_ids': ['5']}]

    def test_distinct_originals_raw_strings_and_missing_coverage(self):
        counts, coverage = raw_name_counts(self.papers, self.source, self.sha)
        self.assertEqual(counts, {'Wei Wang': 2, 'Wei Zhang': 1, 'wei wang': 1})
        self.assertEqual(coverage['known_works'], 2)
        self.assertEqual(coverage['unknown_works'], 2)
        self.assertEqual(coverage['partially_missing_works'], 1)
        self.assertEqual(coverage['distinct_name_strings'], 3)

    def test_source_hash_and_canonical_record_completeness(self):
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            raw_name_counts(self.papers, self.source, '0' * 64)
        with self.assertRaisesRegex(ValueError, 'absent'):
            raw_name_counts([{'id': 'absent', 'rw_ids': ['absent']}], self.source, self.sha)
        with self.assertRaisesRegex(ValueError, 'Invalid canonical'):
            raw_name_counts(self.papers + self.papers, self.source, self.sha)

    def test_duplicate_source_record_fails(self):
        with self.source.open('a') as output:
            output.write('1,Another Name\n')
        with self.assertRaisesRegex(ValueError, 'Duplicate RW'):
            raw_name_counts(self.papers, self.source, digest(self.source.read_bytes()))

    def test_chart_scope_order_and_missing_input_are_explicit(self):
        result = build_chart(self.papers, self.source, self.sha, '2026-09-10', chart, count_row)
        self.assertEqual(result['population_key'], 'B')
        self.assertEqual([row['rank'] for row in result['rows']], [1, 2, 3])
        self.assertEqual(result['rows'][0]['denominator'], 4)
        self.assertEqual(result['quality']['missing_works'], 2)
        unavailable = build_chart(self.papers, None, self.sha, '2026-09-10', chart, count_row)
        self.assertEqual(unavailable['status'], 'not_computed')
        self.assertEqual(unavailable['rows'], [])

    def test_top_twenty_does_not_shrink_the_paper_denominator(self):
        with self.source.open('w', newline='') as output:
            writer = csv.writer(output)
            writer.writerow(['Record ID', 'Author'])
            writer.writerows([[str(index), f'Name {index:02}'] for index in range(30)])
        papers = [{'id': str(index), 'rw_ids': [str(index)]} for index in range(30)]
        result = build_chart(papers, self.source, digest(self.source.read_bytes()), '2026-09-10', chart, count_row)
        self.assertEqual(len(result['rows']), 20)
        self.assertTrue(all(row['denominator'] == 30 for row in result['rows']))
        self.assertEqual(result['association_summary']['distinct_name_strings'], 30)
