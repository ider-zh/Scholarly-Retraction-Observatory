from pathlib import Path
import tempfile
import unittest

import pyarrow.parquet as pq

from taxonomy_ngd import core
from taxonomy_ngd.publish import publish
from taxonomy_ngd.run import worker
from taxonomy_ngd.test_ngd import ProjectionTests
from taxonomy_ngd.tools.verify_release import verify


class PublicationTests(unittest.TestCase):
    def fixture(self, root, duplicate_part=False):
        fixture = ProjectionTests()
        fixture.setUp()
        try:
            table = fixture.table()
            entities = fixture.entities
        finally:
            fixture.tearDown()
        core.save_json(root / 'lookups.json.gz', entities)
        core.save_json(root / 'benchmark/report.json.gz', {'complete': True})
        source = root / 'source.parquet'
        core.parquet(source, table)
        entry = {'path': str(source), 'rows': table.num_rows, 'identity': core.source_identity(source), 'entity': 'works'}
        nodes = []
        for taxonomy, level, identifiers in [('concepts', 0, ['C0']), ('concepts', 1, ['C1']),
                                            ('topics', 0, ['F1', 'F2']), ('topics', 1, ['S1', 'S2'])]:
            for identifier in identifiers:
                parents = [] if level == 0 else (['C0'] if taxonomy == 'concepts' else ['F' + identifier[-1]])
                nodes.append({'taxonomy': taxonomy, 'level': level, 'id': identifier,
                              'name': 'Mathematics' if identifier in ('C0', 'F1') else identifier,
                              'parent_l0_ids': parents, 'parent_relationship_source': 'fixture'})
        edges = [{'taxonomy': node['taxonomy'], 'l1_id': node['id'], 'l0_id': parent, 'relationship_source': 'fixture'}
                 for node in nodes for parent in node['parent_l0_ids']]
        parts = []
        for index in range(2 if duplicate_part else 1):
            parts.append(worker({'run': str(root), 'source': entry, 'destination': str(root / 'staging' / f'part-{index:06d}'),
                                 'definition_hash': 'fixture', 'engine': 'duckdb'}))
        definition = {'identity': 'fixture', 'input': {'inventory': [entry] * len(parts),
                      'nodes': nodes, 'edges': edges, 'snapshot_date': '2026-06-26'}}
        return definition, parts

    def test_full_publish_slices_hashes_and_immutable_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            definition, parts = self.fixture(root)
            completion = publish(root, definition, parts)
            self.assertEqual(completion['N'], 3)
            final = root / 'final'
            quality = core.read_json(final / 'quality_report.json.gz')
            self.assertEqual(quality['full_membership_independent_recount'], 'passed')
            for name, meta in completion['outputs'].items():
                self.assertEqual(core.digest(final / name), meta['sha256'])
            matrix = pq.read_table(final / 'topics_l0_l1_ngd.parquet').to_pylist()
            selected = pq.read_table(final / 'topics_l1_math_distance.parquet').to_pylist()
            for row in selected:
                original = next(item for item in matrix if item['l1_id'] == row['l1_id'] and item['l0_id'] == row['math_l0_id'])
                self.assertEqual(row['ngd_to_math'], original['ngd'])
                self.assertEqual(row['f_math'], original['f_l0'])
                self.assertEqual(row['ngd_rank_excluding_parent'], original['ngd_rank_excluding_parent'])
            self.assertEqual(publish(root, definition, parts), completion)
            self.assertTrue(verify(final)['accepted'])
            (final / 'topics_l0_l1_ngd.parquet').write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                publish(root, definition, parts)

    def test_global_duplicate_blocks_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            definition, parts = self.fixture(root, duplicate_part=True)
            with self.assertRaisesRegex(ValueError, 'Global Work identity'):
                publish(root, definition, parts)
            self.assertFalse((root / 'final/completion.json.gz').exists())

    def test_audit_blocks_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            definition, parts = self.fixture(root)
            parts[0]['audit'].append({'kind': 'unresolved_topic', 'blocking': True, 'rows': 1})
            with self.assertRaisesRegex(ValueError, 'Structural anomalies'):
                publish(root, definition, parts)
            self.assertFalse((root / 'final/completion.json.gz').exists())
