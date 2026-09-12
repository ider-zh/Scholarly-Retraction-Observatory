import unittest

from pipeline.country_analysis import build_explorer


class CountryAnalysisTests(unittest.TestCase):
    def test_legacy_unmerged_denominators_fail_instead_of_being_added(self):
        dimensions = [('institution_country', 'TW', 'article', 2020, 10, 10)]
        with self.assertRaisesRegex(ValueError, 'new dimension scan'):
            build_explorer(dimensions, {}, set(), set(), '2026-06-26', '2026-09-10')

    def test_merged_work_numerator_is_counted_once(self):
        dimensions = [('institution_country', 'CN', 'article', 2020, 10, 10)]
        works = {'first': {'publication_year': 2020, 'countries': {'institution_country': {'countries': ['CN', 'TW']}}}}
        explorer = build_explorer(dimensions, works, {'first'}, set(), '2026-06-26', '2026-09-10')
        self.assertEqual(explorer['nodes'][0]['counts']['A1'][0], 1)
        self.assertEqual(explorer['nodes'][0]['denominator'][0], 10)

    def test_absent_country_dimensions_do_not_advertise_available_analysis(self):
        dimensions = [('primary_field', 'Medicine', 'article', 2020, 1000, 1000)]
        self.assertIsNone(build_explorer(dimensions, {}, set(), set(), '2026-06-26', '2026-09-10'))

    def test_yearly_denominators_deduplication_and_cutoff_scoped_populations(self):
        dimensions = [('institution_country', 'CN', 'article', 2020, 1000, 900),
                      ('institution_country', 'CN', 'article', 2021, 2000, 1900),
                      ('institution_country', 'US', 'article', 2020, 500, 400),
                      ('institution_country', 'CN', 'review', 2020, 999, 999),
                      ('authorship_country', 'CN', 'article', 2020, 9999, 9999)]
        def work(year, countries):
            return {'publication_year': year, 'countries': {'institution_country': {'countries': countries}}}
        works = {'first': work(2020, ['CN', 'CN', 'US']), 'second': work(2021, ['CN']),
                 'missing': work(2020, []), 'early': work(1999, ['CN'])}
        explorer = build_explorer(dimensions, works, set(works), {'second'}, '2026-06-26', '2026-09-10')
        nodes = {node['id']: node for node in explorer['nodes']}
        self.assertEqual(nodes['CN']['denominator'][0], 3000)
        self.assertEqual(nodes['CN']['denominator'][21:23], [1000, 2000])
        self.assertEqual(nodes['CN']['counts']['A1'][0], 2)
        self.assertEqual(nodes['US']['counts']['A1'][0], 1)
        self.assertEqual(nodes['CN']['counts']['C_D'][0], 1)
        self.assertEqual(explorer['missing_country']['A1'][0], 1)
        self.assertEqual(nodes['CN']['counts']['A1'][1], 0)

    def test_country_year_numerator_must_belong_to_same_year_denominator(self):
        dimensions = [('institution_country', 'CN', 'article', 2021, 10, 10)]
        works = {'first': {'publication_year': 2020, 'countries': {'institution_country': {'countries': ['CN']}}}}
        with self.assertRaisesRegex(ValueError, 'annual numerator'):
            build_explorer(dimensions, works, {'first'}, set(), '2026-06-26', '2026-09-10')
        self.assertIsNone(build_explorer([], works, set(), set(), '2026-06-26', '2026-09-10'))
