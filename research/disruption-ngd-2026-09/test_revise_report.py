import copy
import json
import tempfile
import unittest
from pathlib import Path

from revise_report import digest, empirical_signature, revise


class ReaderRevisionTests(unittest.TestCase):
    def original(self, directory):
        evidence = directory / 'evidence.json'
        evidence.write_text('{}')
        slide = dict(section='原报告', title='测试', subtitle='测试', takeaway='测试', source='测试', body=['测试'])
        slides = [copy.deepcopy(slide) for _ in range(37)]
        for entry in slides[30:]:
            entry['appendix'] = True
        slides[5]['chart'] = {'type': 'scatter', 'series': [{'name': '证据', 'points': [{'x': -0.1, 'y': 0.2}]}]}
        slides[9]['table'] = {'columns': ['分子', '分母'], 'rows': [[10, 1000]]}
        payload = dict(status='verified', title='原报告', slides=slides,
                       source_manifests=[{'path': str(evidence), 'sha256': digest(evidence)}])
        source = directory / 'presentation.json'
        source.write_text(json.dumps(payload))
        return payload, source

    def test_preserves_data_and_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            original, source = self.original(Path(temporary))
            before = copy.deepcopy(original)
            revised = revise(original, source)
            self.assertEqual(original, before)
            self.assertEqual(empirical_signature(original['slides'])['figures'], empirical_signature(revised['slides'])['figures'])
            self.assertIn(original['slides'][9]['table'], empirical_signature(revised['slides'])['tables'])
            self.assertEqual(len(revised['slides']), 52)
            self.assertEqual(sum(bool(slide.get('section_break')) for slide in revised['slides']), 4)
            text = json.dumps(revised, ensure_ascii=False)
            for required in ['2021-01-01 至 2025-12-31', '2020-01-01 至 2024-12-31', '本研究未计算', '并列值取平均名次', 'is_retracted=true']:
                self.assertIn(required, text)
            for required in ['不是从撤稿日期倒推五年', '2016—2020', '若2022年撤稿', '若2019年撤稿', '不会把窗口截到2019年', '不删除原记录']:
                self.assertIn(required, text)
            self.assertNotIn('撤稿前窗口', text)

    def test_refuses_changed_evidence_and_double_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            original, source = self.original(Path(temporary))
            revised = revise(original, source)
            with self.assertRaises(ValueError):
                revise(revised, source)
            Path(original['source_manifests'][0]['path']).write_text('changed')
            with self.assertRaises(ValueError):
                revise(original, source)

    def test_teaching_numbers(self):
        from math import log10
        self.assertAlmostEqual((8 - 2) / (8 + 2 + 10), 0.3)
        self.assertAlmostEqual(1 - 6 * 2 / (4 * (4 ** 2 - 1)), 0.8)
        self.assertAlmostEqual((log10(100) - log10(50)) / (log10(1000) - log10(100)), 0.3010299956639812)
        self.assertAlmostEqual((log10(100) - log10(10)) / (log10(1000) - log10(100)), 1)

    def test_group_rules_and_appendix_correlation_pair(self):
        with tempfile.TemporaryDirectory() as temporary:
            original, source = self.original(Path(temporary))
            original['slides'][23]['title'] = '近组与远组：比较的是子学科比例的中位数'
            original['slides'][30]['title'] = '每一个预设口径都留下记录'
            revised = revise(original, source)
            text = json.dumps(revised, ensure_ascii=False)
            for required in ['第33.3%', '第66.7%', '相同距离不拆开', '不是合并分子、分母',
                             '不是NGD相关', 'CD或no-NR', '学科等权']:
                self.assertIn(required, text)
            self.assertEqual(len(revised['slides']), 53)


if __name__ == '__main__':
    unittest.main()
