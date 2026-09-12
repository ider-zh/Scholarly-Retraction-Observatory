import unittest

import duckdb

from pipeline.country_grouping import country_list_sql
from pipeline.snapshot import country_sets
from pipeline.snapshot_report import associations


class CountryGroupingTests(unittest.TestCase):
    def test_group_before_work_deduplication_fraction_and_collaboration(self):
        def work(countries):
            return {'authorships': [{'countries': countries, 'institutions': [
                {'id': 'https://openalex.org/I' + str(index + 1), 'country_code': country}
                for index, country in enumerate(countries)]}]}
        merged, _, _ = country_sets(work(['CN', 'TW', 'TW']))
        international, _, _ = country_sets(work(['CN', 'TW', 'US']))
        for mode in ('institution_country', 'authorship_country'):
            self.assertEqual(merged[mode]['countries'], ['CN'])
            self.assertEqual(merged[mode]['collaboration'], 'completeness_unknown')
            self.assertEqual(international[mode]['countries'], ['CN', 'US'])
            self.assertEqual(international[mode]['collaboration'], 'multi_country_observed')
            counts, weights, _ = associations({'first': merged[mode]['countries'], 'second': international[mode]['countries']})
            self.assertEqual(dict(counts), {'CN': 2, 'US': 1})
            self.assertEqual(dict(weights), {'CN': 1.5, 'US': .5})

    def test_dimension_denominators_merge_before_unrolling_and_weighting(self):
        with duckdb.connect() as connection:
            rows = connection.execute(f'''
                WITH source(countries) AS (VALUES (['CN', 'TW']), (['TW']), (['TW', 'CN', 'US']), ([])),
                grouped AS (SELECT {country_list_sql('countries')} AS countries FROM source)
                SELECT country, count(*), sum(weight)
                FROM (SELECT unnest(countries) AS country, 1.0 / len(countries) AS weight FROM grouped)
                GROUP BY country ORDER BY country
            ''').fetchall()
        self.assertEqual(rows, [('CN', 3, 2.5), ('US', 1, .5)])
