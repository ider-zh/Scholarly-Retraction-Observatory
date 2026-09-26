import gzip
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import graph_bridge as bridge


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        nodes = pa.table({'work_id_numeric': pa.array([1, 2, 3], type=pa.uint64()),
                          'publication_year': pa.array([2020, None, 1900], type=pa.int32()),
                          'openalex_cited_by_count': pa.array([5, None, 0], type=pa.int64()),
                          'reference_count_raw': pa.array([5, None, 0], type=pa.int64())})
        references = pa.table({'work_id': ['https://openalex.org/W1', 'https://openalex.org/W2', 'https://openalex.org/W3'],
                               'referenced_works': pa.array([['https://openalex.org/W3', 'https://openalex.org/W3', None, 'bad', 'https://openalex.org/W18446744073709551616'], None, []], type=pa.list_(pa.string()))})
        pq.write_table(nodes, self.source / 'nodes.parquet')
        pq.write_table(references, self.source / 'raw_references.parquet')
        checkpoint = {'rows': 3, 'source': 'works/fixture.parquet', 'status': 'complete', 'config_sha256': 'foundation-fixture',
                      'outputs': {name: {'sha256': bridge.digest_file(self.source / name)} for name in ('nodes.parquet', 'raw_references.parquet')}}
        bridge.atomic_json(self.source / 'complete.json', checkpoint)
        self.task = {'source': str(self.source), 'destination': str(self.root / 'output'),
                     'checkpoint_sha256': bridge.digest_file(self.source / 'complete.json'),
                     'config_sha256': 'test', 'minimum_free': 0, 'foundation_config_sha256': 'foundation-fixture'}

    def tearDown(self):
        self.directory.cleanup()

    def test_binary_roundtrip_and_resume(self):
        first = bridge.convert_shard(self.task)
        self.assertEqual(first['rows'], 3)
        self.assertEqual(first['raw_reference_entries'], 5)
        with gzip.open(self.root / 'output/nodes.bin.gz', 'rb') as stream:
            self.assertEqual(list(bridge.NODE.iter_unpack(stream.read())), [(1, 2020, 0, 5, 5), (2, 0, 0, -1, -1), (3, 1900, 0, 0, 0)])
        with gzip.open(self.root / 'output/references.bin.gz', 'rb') as stream:
            self.assertEqual(bridge.HEADER.unpack(stream.read(16)), (1, 5))
            self.assertEqual(struct.unpack('<5Q', stream.read(40)), (3, 3, 0, 0, 0))
            self.assertEqual(bridge.HEADER.unpack(stream.read(16)), (2, -1))
            self.assertEqual(bridge.HEADER.unpack(stream.read(16)), (3, 0))
            self.assertEqual(stream.read(), b'')
        self.assertEqual(bridge.convert_shard(self.task), first)

    def test_corrupted_foundation_is_rejected(self):
        with (self.source / 'raw_references.parquet').open('ab') as stream:
            stream.write(b'bad')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            bridge.convert_shard(self.task)

    def test_corrupted_bridge_is_rejected(self):
        bridge.convert_shard(self.task)
        (self.root / 'output/nodes.bin.gz').write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            bridge.convert_shard(self.task)

    def test_foreign_foundation_configuration_is_rejected(self):
        self.task['foundation_config_sha256'] = 'other-config'
        with self.assertRaisesRegex(ValueError, 'another configuration'):
            bridge.convert_shard(self.task)


if __name__ == '__main__':
    unittest.main()
