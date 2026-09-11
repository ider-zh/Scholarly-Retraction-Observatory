import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

try:
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
except ModuleNotFoundError as error:
    raise unittest.SkipTest('Install pipeline/snapshot_requirements.txt for snapshot tests') from error

from pipeline.validate_snapshot import (
    PREFIX, atomic_json, digest, identity_audit, inspect_file,
    manifest_entries, transfer_gate, validate,
)


class SnapshotValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'source'
        self.root.mkdir()
        self.output = Path(self.temporary.name) / 'audit'
        self.work = self.root / 'works/updated_date=2026-06-26/part_0000.parquet'
        self.work.parent.mkdir(parents=True)
        authorship = pa.struct([
            ('author', pa.struct([('id', pa.string())])),
            ('countries', pa.list_(pa.string())),
            ('institutions', pa.list_(pa.struct([('id', pa.string()), ('country_code', pa.string())]))),
        ])
        topic = pa.struct([('id', pa.string())] + [
            (level, pa.struct([('id', pa.string())])) for level in ('domain', 'field', 'subfield')
        ])
        self.table = pa.table({
            'id': ['https://openalex.org/W1', 'https://openalex.org/W2', 'https://openalex.org/W3'],
            'doi': ['10.1234/shared', '10.1234/shared', None],
            'ids': pa.array([[], [], []], type=pa.map_(pa.string(), pa.string())),
            'publication_date': pa.array([dt.date(2020, 1, 1)] * 3, type=pa.date32()),
            'publication_year': [2020] * 3, 'type': ['article'] * 3,
            'authorships': pa.array([[], [], []], type=pa.list_(authorship)),
            'primary_topic': pa.array([None] * 3, type=topic),
            'is_retracted': pa.array([True, False, None], type=pa.bool_()),
            'is_xpac': pa.array([False, True, None], type=pa.bool_()),
        })
        pq.write_table(self.table, self.work)
        size = self.work.stat().st_size
        self.entry = {'url': PREFIX + str(self.work.relative_to(self.root)),
                      'meta': {'record_count': 3, 'content_length': size}}
        self.manifest = {'date': '2026-06-26', 'format': 'parquet',
                         'meta': {'record_count': 3, 'content_length': size},
                         'entities': [{'entity': 'works', 'record_count': 3,
                                       'content_length': size, 'files': [self.entry]}]}
        atomic_json(self.root / 'manifest.json', self.manifest)

    def test_manifest_totals_and_path_safety(self):
        self.assertEqual(len(manifest_entries(self.manifest)), 1)
        for url in (PREFIX + '../escape.parquet', PREFIX + 'works/../escape.parquet',
                    's3://other/works/part.parquet', PREFIX + 'authors/part.parquet'):
            invalid = copy.deepcopy(self.manifest)
            invalid['entities'][0]['files'][0]['url'] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                manifest_entries(invalid)
        invalid = copy.deepcopy(self.manifest)
        invalid['meta']['record_count'] += 1
        with self.assertRaises(ValueError):
            manifest_entries(invalid)

    def test_duplicate_manifest_file_rejected(self):
        self.manifest['entities'][0]['files'].append(self.entry)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            manifest_entries(self.manifest)

    def test_missing_corrupt_and_wrong_row_count(self):
        entry = manifest_entries(self.manifest)[0]
        inspected, schema = inspect_file(self.root, dict(entry, record_count=4))
        self.assertIn('row_count_mismatch', inspected['errors'])
        self.assertIsNotNone(schema)
        self.work.write_bytes(b'not parquet')
        inspected, schema = inspect_file(self.root, entry)
        self.assertIn('size_mismatch', inspected['errors'])
        self.assertIsNone(schema)
        self.work.unlink()
        self.assertIn('missing_file', inspect_file(self.root, entry)[0]['errors'])

    def test_duplicate_ids_block_without_deduplication(self):
        duplicate = self.table.set_column(0, 'id', pa.array(['https://openalex.org/W1'] * 3))
        pq.write_table(duplicate, self.work)
        with duckdb.connect() as connection:
            result = identity_audit(connection, [str(self.work)], 'works')
        self.assertEqual(result['records'], 3)
        self.assertEqual(result['unique_ids'], 1)
        self.assertEqual(result['duplicate_excess'], 2)

    def test_all_flag_states_and_corpus_unknown_preserved(self):
        with duckdb.connect() as connection:
            result = identity_audit(connection, [str(self.work)], 'works')
        self.assertEqual(result['duplicate_excess'], 0)
        self.assertEqual(result['flag_states'], [
            {'is_retracted': False, 'is_xpac': True, 'records': 1},
            {'is_retracted': True, 'is_xpac': False, 'records': 1},
            {'is_retracted': None, 'is_xpac': None, 'records': 1},
        ])

    def test_blank_and_null_ids_do_not_make_negative_duplicate_counts(self):
        table = self.table.set_column(0, 'id', pa.array(['https://openalex.org/W1', '', None]))
        pq.write_table(table, self.work)
        with duckdb.connect() as connection:
            result = identity_audit(connection, [str(self.work)], 'works')
        self.assertEqual(result['missing_ids'], 2)
        self.assertEqual(result['unique_ids'], 1)
        self.assertEqual(result['duplicate_excess'], 0)

    def test_transfer_requires_real_manifest_and_ordered_timestamps(self):
        transfer = self.root / 'transfer.json'
        value = {'source_prefix': PREFIX, 'pre_transfer_manifest': 'manifest.json',
                 'manifest_captured_at': '2026-09-09T00:00:00+00:00',
                 'retrieval_started_at': '2026-09-09T00:01:00+00:00',
                 'retrieval_completed_at': '2026-09-10T00:00:00+00:00'}
        atomic_json(transfer, value)
        manifest_hash = digest((self.root / 'manifest.json').read_bytes())
        self.assertEqual(transfer_gate(transfer, manifest_hash, '2026-09-11T00:00:00+00:00')['status'], 'passed')
        value['retrieval_completed_at'] = '2026-09-08T00:00:00+00:00'
        atomic_json(transfer, value)
        self.assertEqual(transfer_gate(transfer, manifest_hash, '2026-09-11T00:00:00+00:00')['status'], 'failed')
        self.assertEqual(transfer_gate(None, manifest_hash, '2026-09-11T00:00:00+00:00')['status'], 'missing')

    def test_unlisted_files_excluded_failed_attempt_preserves_success(self):
        pq.write_table(self.table, self.work.parent / 'stale.parquet')
        atomic_json(self.output / 'validated-source.json', {'report': 'previous-success'})
        result = validate(self.root, self.output, scan_ids=True)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['source_accounting']['unlisted_files_excluded'], 1)
        self.assertEqual(result['entities']['works']['identity']['records'], 3)
        self.assertEqual(json.loads((self.output / 'validated-source.json').read_text()), {'report': 'previous-success'})
        with patch('pipeline.validate_snapshot.identity_audit', wraps=identity_audit) as scan:
            repeat = validate(self.root, self.output, scan_ids=True)
        self.assertEqual(scan.call_count, 1)
        self.assertTrue(repeat['entities']['works']['identity_checkpoint_reused'])
        pq.write_table(self.table, self.work)
        with patch('pipeline.validate_snapshot.identity_audit', side_effect=[result['benchmark']['result'], RuntimeError('input changed')]):
            changed = validate(self.root, self.output, scan_ids=True)
        self.assertIn('works:identity_scan_failed', changed['blockers'])
        self.assertEqual(changed['entities']['works']['identity']['reason'], 'input changed')

    def test_schema_flag_strings_fail_closed(self):
        table = self.table.set_column(self.table.schema.get_field_index('is_xpac'),
                                      'is_xpac', pa.array(['false', 'true', None]))
        pq.write_table(table, self.work)
        result = validate(self.root, self.output, scan_ids=True)
        self.assertIn('works:file_errors', result['blockers'])
        self.assertIn('identity_scan_not_completed', result['blockers'])

    def test_verified_source_promotion_and_changed_remote(self):
        transfer = self.root / 'transfer.json'
        atomic_json(transfer, {
            'source_prefix': PREFIX, 'pre_transfer_manifest': 'manifest.json',
            'manifest_captured_at': '2026-06-27T00:00:00+00:00',
            'retrieval_started_at': '2026-06-28T00:00:00+00:00',
            'retrieval_completed_at': '2026-06-29T00:00:00+00:00',
        })
        remote = MagicMock()
        remote.__enter__.return_value.read.return_value = (self.root / 'manifest.json').read_bytes()
        with patch('urllib.request.urlopen', return_value=remote):
            result = validate(self.root, self.output, scan_ids=True, check_remote=True, transfer=transfer)
        self.assertEqual(result['status'], 'validated')
        pointer = (self.output / 'validated-source.json').read_bytes()
        remote.__enter__.return_value.read.return_value = b'changed upstream manifest'
        with patch('urllib.request.urlopen', return_value=remote):
            changed = validate(self.root, self.output, scan_ids=True, check_remote=True, transfer=transfer)
        self.assertIn('post_transfer_manifest_not_verified', changed['blockers'])
        self.assertEqual((self.output / 'validated-source.json').read_bytes(), pointer)


if __name__ == '__main__':
    unittest.main()
