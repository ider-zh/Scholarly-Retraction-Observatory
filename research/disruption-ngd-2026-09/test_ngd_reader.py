import copy
import unittest

from ngd_reader import annotate_panorama, average_ranks


class NgdReaderTests(unittest.TestCase):
    def test_average_ranks_with_ties(self):
        self.assertEqual(average_ranks([3, 1, 1, 4]), [3, 1.5, 1.5, 4])

    def fixture(self):
        import statistics
        series, rows = [], []
        for taxonomy, values in [('concepts', [1, 5, 6, 3, 4, 2]), ('topics', [6, 2, 1, 4, 3, 5])]:
            points = [dict(x=index, y=value, subject=str(index)) for index, value in enumerate(values)]
            series.append(dict(name=taxonomy + ' · 撤稿n≥20', points=points))
            rows.append(dict(taxonomy=taxonomy, reference='Mathematics', scope='all_unique_children',
                             children=6, spearman_crude=statistics.correlation(list(range(6)), values)))
        return dict(source='test', chart=dict(series=series)), rows

    def test_annotations_keep_chart_and_bind_coefficients(self):
        slide, rows = self.fixture()
        original = copy.deepcopy(slide)
        revised = annotate_panorama(slide, rows)
        self.assertEqual(slide, original)
        self.assertEqual(revised['chart'], slide['chart'])
        self.assertIn('ρ=-0.029', revised['subtitle'])
        self.assertIn('ρ=+0.029', revised['subtitle'])
        self.assertIn('不是按颜色分组', revised['source'])

    def test_refuses_mismatch_without_mutation(self):
        slide, rows = self.fixture()
        original = copy.deepcopy(slide)
        rows[0]['spearman_crude'] = 0.5
        with self.assertRaises(ValueError):
            annotate_panorama(slide, rows)
        self.assertEqual(slide, original)

    def test_refuses_missing_subject(self):
        slide, rows = self.fixture()
        slide['chart']['series'][0]['points'].pop()
        with self.assertRaises(ValueError):
            annotate_panorama(slide, rows)


if __name__ == '__main__':
    unittest.main()
