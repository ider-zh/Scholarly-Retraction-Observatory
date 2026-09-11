import unittest

from pipeline.concept_analysis import concept_members
from pipeline.report_language import format_value, readable


class ReaderMethodsTests(unittest.TestCase):
    def test_integral_counts_and_fractional_units(self):
        for unit in ('works', 'records', 'edges', 'authors'):
            self.assertEqual(format_value(50331.0, unit), '50,331')
            with self.assertRaises(ValueError):
                format_value(1.5, unit)
        self.assertEqual(format_value(1.5, 'work_equivalents'), '1.50')

    def test_population_language_does_not_replace_inside_identifiers(self):
        self.assertEqual(readable('A1'), '筛选后的撤稿标记论文')
        self.assertEqual(readable('A1_over_D'), '撤稿标记论文 / 同口径发表论文')
        self.assertEqual(readable('excluded_work_type'), '不属研究论文类型')
        self.assertEqual(readable('A10'), 'A10')

    def test_concepts_are_deduplicated_at_each_level_including_zero_score(self):
        values = [{'id': 'https://openalex.org/C1', 'level': 0, 'score': 0, 'display_name': 'Physics'}] * 2
        values += [{'id': 'https://openalex.org/C2', 'level': 1}, {'id': 'https://openalex.org/T1', 'level': 0}]
        self.assertEqual(concept_members(values, 0), {'https://openalex.org/C1': 'Physics'})
        self.assertEqual(concept_members(values, 1), {'https://openalex.org/C2': 'https://openalex.org/C2'})
        self.assertEqual(concept_members(None, 0), {})
