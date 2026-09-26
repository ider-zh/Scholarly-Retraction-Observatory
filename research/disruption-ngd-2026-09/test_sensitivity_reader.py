import copy
import unittest

from sensitivity_reader import LABELS, canonical_chart, enhance


class SensitivityReaderTests(unittest.TestCase):
    def evidence(self):
        definitions = [
            ('ex', '5y', 10, 5, 'cd'), ('ex', '5y', 1, 0, 'cd'),
            ('ex', '5y', 5, 5, 'cd'), ('ex', '5y', 20, 5, 'cd'),
            ('ex', '5y', 10, 0, 'cd'), ('ex', '5y', 10, 10, 'cd'),
            ('ex', '3y', 10, 5, 'cd'), ('ex', '10y', 10, 5, 'cd'),
            ('ex', 'lifetime', 10, 5, 'cd'), ('in', '5y', 10, 5, 'cd'),
            ('ex', '5y', 10, 5, 'no_nr'),
        ]
        variants = [[name, *definition] for name, definition in zip(LABELS, definitions)]
        values = [('concepts_l1', 'Concepts 子学科', [.048, -.139, -.001, .085, -.002, .070, .074, .014, .047, .061, .158]),
                  ('topics_subfield', 'Topics 子学科', [-.211, -.457, -.286, -.164, -.309, -.198, -.174, -.273, -.243, -.189, -.088])]
        stats = {'cd_correlations': []}
        series = []
        for taxonomy, name, coefficients in values:
            points = []
            for identifier, coefficient in zip(LABELS, coefficients):
                points.append({'x': identifier, 'subject': identifier, 'y': coefficient})
                stats['cd_correlations'].append({'taxonomy': taxonomy, 'variant': identifier,
                                                 'rho': coefficient, 'subjects': 284 if taxonomy == 'concepts_l1' else 248})
            series.append({'name': name, 'points': points})
        slide = {'chart': {'type': 'bar', 'x_label': '旧标签', 'y_label': '旧标签', 'series': series, 'y_min': -1, 'y_max': 1}}
        return slide, stats, variants

    def test_labels_and_conditions_preserve_measurements(self):
        slide, stats, variants = self.evidence()
        original = copy.deepcopy(slide)
        pages, summary = enhance(slide, stats, variants)
        self.assertEqual(slide, original)
        self.assertEqual(canonical_chart(slide['chart']), canonical_chart(pages[2]['chart']))
        self.assertEqual(summary['topics_subfield']['negative'], 11)
        self.assertEqual(summary['concepts_l1']['positive'], 8)
        self.assertEqual(pages[0]['table']['rows'][1][2:4], ['≥1', '≥0'])
        self.assertEqual(pages[1]['table']['rows'][3][1], '2011年至2026-06-26快照')
        self.assertEqual(pages[1]['table']['rows'][4][1], '2010–2014；含发表年的5年')
        self.assertIn('参考≥20＋10年', pages[3]['body'][-1])

    def test_rejects_mismatched_data(self):
        slide, stats, variants = self.evidence()
        slide['chart']['series'][0]['points'][0]['y'] = .9
        with self.assertRaises(ValueError):
            enhance(slide, stats, variants)

    def test_direction_claim_is_guarded(self):
        slide, stats, variants = self.evidence()
        slide['chart']['series'][1]['points'][0]['y'] = .5
        next(row for row in stats['cd_correlations'] if row['taxonomy'] == 'topics_subfield')['rho'] = .5
        with self.assertRaises(ValueError):
            enhance(slide, stats, variants)

    def test_numeric_changes_are_not_label_changes(self):
        slide, _, _ = self.evidence()
        changed = copy.deepcopy(slide['chart'])
        changed['series'][0]['points'][0]['y'] += .1
        self.assertNotEqual(canonical_chart(slide['chart']), canonical_chart(changed))


if __name__ == '__main__':
    unittest.main()
