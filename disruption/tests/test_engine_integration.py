import gzip
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'disruption/src'))
import graph_bridge as bridge
from disruption.reference.oracle import ReferenceGraph
from disruption.reference.test_oracle import fixture
import window_results


@unittest.skipUnless(shutil.which('go'), 'Go required for cross-engine checks')
class EngineIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        cls.executable = cls.root / 'engine'
        subprocess.run(['go', 'build', '-o', str(cls.executable), '.'], cwd=ROOT / 'disruption/engine', check=True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def check_graph(self, works, name):
        directory = self.root / name
        source = directory / 'source'
        source.mkdir(parents=True)
        identifiers = [int(work['id'].removeprefix('W')) for work in works]
        normalize = lambda value: 'https://openalex.org/' + value if value and value.startswith('W') else value
        raw = [None if work.get('referenced_works') is None else [normalize(value) for value in work['referenced_works']] for work in works]
        nodes = pa.table({'work_id_numeric': pa.array(identifiers, type=pa.uint64()),
                          'publication_year': pa.array([work.get('year') for work in works], type=pa.int32()),
                          'openalex_cited_by_count': pa.array([work.get('cited_by_count') for work in works], type=pa.int64()),
                          'reference_count_raw': pa.array([None if values is None else len(values) for values in raw], type=pa.int64())})
        references = pa.table({'work_id': ['https://openalex.org/W' + str(identifier) for identifier in identifiers],
                               'referenced_works': pa.array(raw, type=pa.list_(pa.string()))})
        pq.write_table(nodes, source / 'nodes.parquet')
        pq.write_table(references, source / 'raw_references.parquet')
        saved = {'rows': len(works), 'source': 'fixture', 'status': 'complete', 'config_sha256': 'fixture', 'outputs': {name: {'sha256': bridge.digest_file(source / name)} for name in ('nodes.parquet', 'raw_references.parquet')}}
        bridge.atomic_json(source / 'complete.json', saved)
        converted = directory / 'bridge'
        record = bridge.convert_shard({'source': str(source), 'destination': str(converted),
                                       'checkpoint_sha256': bridge.digest_file(source / 'complete.json'), 'config_sha256': 'fixture', 'minimum_free': 0, 'foundation_config_sha256': 'fixture'})
        manifest = {'schema_version': 'graph-bridge-v1', 'status': 'complete', 'snapshot_date': '2026-06-26',
                    'foundation_config_sha256': 'fixture', 'rows': len(works),
                    'shards': [{**record, 'nodes': 'nodes.bin.gz', 'references': 'references.bin.gz'}]}
        bridge.atomic_json(converted / 'manifest.json', manifest)
        graph_path, count_path = directory / 'graph', directory / 'counts'
        subprocess.run([str(self.executable), 'build', '--input', str(converted / 'manifest.json'), '--output', str(graph_path)], check=True, capture_output=True)
        subprocess.run([str(self.executable), 'count', '--graph', str(graph_path), '--output', str(count_path), '--all', '--workers', '3', '--partition-size', '7', '--minimum-free-bytes', '0'], check=True, capture_output=True)
        records = {}
        for path in count_path.rglob('*.jsonl.gz'):
            with gzip.open(path, 'rt') as stream:
                for line in stream:
                    row = json.loads(line)
                    records[row['work_id']] = row
        self.assertEqual(len(records), len(works))
        oracle = ReferenceGraph(works, '2026-06-26')
        keys = ['reference_count_raw', 'reference_count_valid', 'reference_count_resolved_unique', 'graph_indegree_all',
                'incoming_same_year_count', 'incoming_earlier_year_count', 'incoming_unknown_year_count']
        for identifier, actual in records.items():
            expected = oracle.annual(identifier)
            for key in keys:
                self.assertEqual(actual[key], expected[key], (identifier, key))
            self.assertEqual(actual['reference_quality_counts'], expected['reference_quality_counts'])
            observed = {row['age_year']: row for row in actual['annual_counts']}
            for row in expected['annual_counts']:
                for key in ['NF', 'NB', 'NR', 'citation_count', 'future_related_count']:
                    self.assertEqual(observed.get(row['age_year'], {}).get(key, 0), row[key], (identifier, key, row['age_year']))
        manifest = json.loads((count_path / 'manifest.json').read_text())
        windows = []
        for index in range(len(manifest['partitions'])):
            destination = directory / 'analytical' / str(index)
            window_results.materialize(count_path / 'manifest.json', destination, partition_index=index)
            windows.extend(pq.ParquetFile(destination / 'windows.parquet').read().to_pylist())
        self.assertEqual(len(windows), len(works) * 8)
        for row in windows:
            annual = oracle.annual(row['work_id'])
            years = 'lifetime' if row['window'] == 'lifetime' else int(row['window'].removesuffix('y'))
            expected = oracle.window(annual, row['window_policy'], years)
            for key in ['NF', 'NB', 'NR', 'citation_count', 'is_mature', 'disruption_cd', 'disruption_no_nr']:
                self.assertEqual(row[key], expected[key], (row['work_id'], row['window_policy'], row['window'], key))
        return directory, records

    def test_acceptance_graph(self):
        self.check_graph(fixture(), 'acceptance')

    def test_randomized_graph_with_anomalies(self):
        generator = random.Random(42)
        works = []
        for identifier in range(1, 81):
            targets = [f'W{generator.randrange(1, 90)}' for _ in range(generator.randrange(0, 15))]
            if identifier % 11 == 0:
                targets.extend(['invalid', None])
            if identifier % 17 == 0:
                targets.extend([f'W{identifier}', f'W{identifier}', 'W999', 'W999'])
            works.append({'id': f'W{identifier}', 'year': generator.choice([None, 0, 2010, 2019, 2020, 2025, 2026, 2030]),
                          'referenced_works': targets if identifier % 13 else None})
        self.check_graph(works, 'random')


if __name__ == '__main__':
    unittest.main()
