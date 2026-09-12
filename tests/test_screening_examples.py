import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location('screening_sampler', Path(__file__).resolve().parents[1] / 'scripts/sample-screening-exclusions.py')
sampler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sampler)


class ScreeningExampleTests(unittest.TestCase):
    def test_exclusion_order_matches_type_then_identity_then_date(self):
        record = {'type': 'review', 'document_role': 'conflict', 'publication_year': 2099, 'publication_date': '2099-01-01'}
        self.assertEqual(sampler.exclusion(record, '2026-06-26'), 'excluded_work_type')
        record['type'] = 'article'
        self.assertEqual(sampler.exclusion(record, '2026-06-26'), 'excluded_conflict')
        record['document_role'] = 'unresolved'
        self.assertEqual(sampler.exclusion(record, '2026-06-26'), 'excluded_date')

    def test_original_supported_and_unresolved_can_be_retained(self):
        for role in ['original_supported', 'unresolved']:
            record = {'type': 'article', 'document_role': role, 'publication_year': 2020, 'publication_date': None}
            self.assertEqual(sampler.exclusion(record, '2026-06-26'), 'retained_A1')
        record['document_role'] = 'suspected_notice'
        self.assertEqual(sampler.exclusion(record, '2026-06-26'), 'excluded_suspected_notice')
