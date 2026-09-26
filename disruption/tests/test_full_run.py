import unittest

from disruption.full_run import verify_coverage


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.graph = {'status': 'complete', 'node_count': 2}
        self.foundation = {'rows': 2}
        self.annual = {'complete': True, 'scope': 'all_graph_works', 'requested_focal_count': 2,
                       'graph_work_count': 2, 'partitions': [{'rows': 2}]}
        self.analytical = {'complete': True, 'scope': 'all_graph_works', 'focal_rows': 2,
                          'window_rows': 16, 'partitions': [{}]}

    def test_full_coverage_only(self):
        self.assertEqual(verify_coverage(self.graph, self.annual, self.analytical, self.foundation), 2)
        self.annual['scope'] = 'selected_focals_full_graph_neighborhood'
        with self.assertRaisesRegex(ValueError, 'annual coverage'):
            verify_coverage(self.graph, self.annual, self.analytical, self.foundation)

    def test_missing_windows_rejected(self):
        self.analytical['window_rows'] = 8
        with self.assertRaisesRegex(ValueError, 'Analytical coverage'):
            verify_coverage(self.graph, self.annual, self.analytical, self.foundation)

    def test_incomplete_graph_rejected(self):
        self.graph['status'] = 'partial'
        with self.assertRaisesRegex(ValueError, 'Graph'):
            verify_coverage(self.graph, self.annual, self.analytical, self.foundation)


if __name__ == '__main__':
    unittest.main()
