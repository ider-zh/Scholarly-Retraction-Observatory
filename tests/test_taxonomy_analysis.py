import io
import pickle
import unittest

from pipeline.aggregate_codec import pack_chart
from pipeline.concept_tree_reference import PrimitiveUnpickler
from pipeline.taxonomy_analysis import subject_nodes


class TaxonomyAnalysisTests(unittest.TestCase):
    def test_subject_parent_deduplicates_siblings_and_dates(self):
        papers = [{'published': '2020-01-01', 'subjects': ['(HSC) Medicine - A', '(HSC) Medicine - B', '(HSC) Medicine - A']},
                  {'published': None, 'subjects': []}]
        taxonomy = subject_nodes(papers, [2020, 2021])
        parent = next(node for node in taxonomy['nodes'] if node['id'] == 'rw-HSC')
        self.assertEqual(parent['counts']['B'], [1, 1, 0])
        self.assertEqual(taxonomy['counts']['B'], [2, 1, 0])
        self.assertIsNone(taxonomy['denominator'])
        self.assertEqual(len([node for node in taxonomy['nodes'] if node['parents'] == ['rw-HSC']]), 2)

    def test_columnar_encoding_preserves_nulls_and_requires_uniform_keys(self):
        chart = {'rows': [{'id': str(index), 'value': None if index == 0 else index} for index in range(50)]}
        packed = pack_chart(chart)
        self.assertNotIn('rows', packed)
        self.assertEqual([dict(zip(packed['row_columns'], row)) for row in packed['row_values']], chart['rows'])
        chart['rows'][0]['extra'] = 1
        self.assertIs(pack_chart(chart), chart)

    def test_official_artifact_reader_cannot_resolve_executable_globals(self):
        self.assertEqual(PrimitiveUnpickler(io.BytesIO(pickle.dumps({1: [2, 3]}))).load(), {1: [2, 3]})
        with self.assertRaises(ValueError):
            PrimitiveUnpickler(io.BytesIO(pickle.dumps(eval))).load()
