import json
from pathlib import Path
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq

from pipeline.broad_snapshot import derive
from pipeline.validate_snapshot import digest


class BroadDerivationTests(unittest.TestCase):
    def test_derivation_retains_types_and_conserves_cohorts_without_mutating_parent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            validation = root / 'validation.json'
            validation.write_text(json.dumps({'status': 'validated', 'blockers': [], 'oa_snapshot_date': '2026-06-26'}))
            (root / 'files.json').write_text(json.dumps([{'entity': 'works', 'key': 'works/part.parquet'}]))
            (source / 'provenance.json').write_text(json.dumps({'config': {'role_policy': 'old'}, 'config_sha256': 'parent', 'validation_report': str(validation)}))
            (source / 'scan-complete.json').write_text(json.dumps({'config_sha256': 'parent', 'files': 1}))
            (source / 'rw_original.json').write_text('[]')
            (source / 'rw_notice.json').write_text(json.dumps([{'doi': '10.1234/notice', 'pmid': None, 'original_ids': ['doi:10.1234/original']}]))
            shard = source / 'shards' / digest(b'works/part.parquet')
            shard.mkdir(parents=True)
            (shard / 'complete.json').write_text(json.dumps({'config_sha256': 'parent'}))
            rows = [dict(id='W1', doi='10.1234/notice', pmid=None, type='retraction', is_xpac=False, is_retracted=True, publication_year=2020, publication_date=None, document_role='known_notice', original_evidence=False, notice_evidence=True, title_suspected=True),
                    dict(id='W2', doi='10.1234/review', pmid=None, type='review', is_xpac=False, is_retracted=True, publication_year=2020, publication_date=None, document_role='suspected_notice', original_evidence=False, notice_evidence=False, title_suspected=True)]
            pq.write_table(pa.Table.from_pylist(rows), shard / 'identifiers.parquet')
            cohorts = [{**{key: row[key] for key in ('is_xpac', 'type', 'publication_year', 'document_role', 'is_retracted')}, 'date_eligible': True, 'work_count': 1} for row in rows]
            cohorts.append(dict(is_xpac=False, type='book', publication_year=2020, document_role='suspected_notice', is_retracted=False, date_eligible=True, work_count=10))
            pq.write_table(pa.Table.from_pylist(cohorts), shard / 'cohorts.parquet')
            pq.write_table(pa.table({'id': ['W1', 'W2']}), shard / 'targets.parquet')
            before = {path.name: path.read_bytes() for path in shard.iterdir()}
            result = derive(source, root / 'broad', workers=1)
            transformed = pq.read_table(result / 'shards' / shard.name / 'identifiers.parquet').to_pylist()
            self.assertEqual([(row['type'], row['document_role']) for row in transformed], [('retraction', 'known_notice'), ('review', 'unresolved')])
            counts = pq.read_table(result / 'shards' / shard.name / 'cohorts.parquet').to_pylist()
            self.assertEqual(sum(row['work_count'] for row in counts), 12)
            self.assertEqual(sum(row['work_count'] for row in counts if row['document_role'] != 'known_notice'), 11)
            self.assertEqual(before, {path.name: path.read_bytes() for path in shard.iterdir()})
