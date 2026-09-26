import copy
import unittest

from disruption_reader import conclusion, scatter_explanation


class DisruptionReaderTests(unittest.TestCase):
    def contrasts(self):
        series = []
        rows = []
        for name, taxonomy in [('Concepts 子学科', 'concepts_l1'), ('Topics 子学科', 'topics_subfield')]:
            series.append({'name': name, 'points': [{'x': 0.01, 'y': 0.008}, {'x': 0.001, 'y': -0.001}]})
            for crude, adjusted in [(0.01, 0.008), (0.001, -0.001)]:
                rows.append(dict(taxonomy=taxonomy, crude_difference=crude,
                                 adjusted_difference=adjusted, common_retracted=20))
        return {'chart': {'type': 'scatter', 'series': series}, 'source': '证据'}, {'year_type_cd_contrasts': rows}

    def test_scatter_descriptions_preserve_points(self):
        slide, evidence = self.contrasts()
        original = copy.deepcopy(slide)
        revised, explanation, summaries = scatter_explanation(slide, evidence)
        self.assertEqual(slide, original)
        self.assertEqual(revised['chart'], original['chart'])
        self.assertEqual(summaries['concepts_l1']['positive'], 1)
        self.assertEqual(summaries['concepts_l1']['same_sign'], 1)
        self.assertEqual(summaries['concepts_l1']['lower'], 2)
        self.assertIn('不是逐篇配对', explanation['body'][0])

    def test_scatter_rejects_changed_coordinates(self):
        slide, evidence = self.contrasts()
        slide['chart']['series'][0]['points'][0]['y'] += 0.1
        with self.assertRaises(ValueError):
            scatter_explanation(slide, evidence)

    def correlations(self):
        rows = []
        for taxonomy, rho in [('concepts_l0', -0.444), ('concepts_l1', 0.048),
                              ('topics_field', -0.049), ('topics_subfield', -0.211)]:
            for number in range(11):
                value = -0.1 if taxonomy == 'concepts_l1' and number == 1 else rho
                rows.append(dict(taxonomy=taxonomy, variant='main_cd5_r10_c5' if number == 0 else str(number),
                                 rho=value, subjects=19, rate_2000_2020_rho=-0.5))
        return {'cd_correlations': rows}

    def test_conclusion_binds_main_values(self):
        page = conclusion(self.correlations())
        self.assertIn('ρ=-0.444', page['body'][0])
        self.assertIn('ρ=-0.049', page['body'][2])
        self.assertIn('不是跨学科通用规律', page['title'])

    def test_conclusion_refuses_stale_direction_claim(self):
        evidence = self.correlations()
        evidence['cd_correlations'][1]['rho'] = 0.2
        with self.assertRaises(ValueError):
            conclusion(evidence)


if __name__ == '__main__':
    unittest.main()
