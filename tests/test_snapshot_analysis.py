import csv
import json
from pathlib import Path
import tempfile
import unittest
import shutil
import subprocess
from unittest.mock import MagicMock, patch

try:
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
except ModuleNotFoundError as error:
    raise unittest.SkipTest('Install snapshot requirements') from error

from pipeline.snapshot import canonicalize_rw, cohort_rate, country_sets, pmid, select_match, scan_snapshot
from pipeline.snapshot_report import associations, build
from pipeline.validate_snapshot import atomic_json, digest, validate
from pipeline.publish_snapshot import publish
from pipeline.snapshot_dimensions import run as dimension_scan
from pipeline.snapshot_citations import run as citation_scan
from pipeline.snapshot_supplement import run as supplement_scan


def source_row(identifier, original='10.1234/original', notice='10.1234/notice', **extra):
    return {'Record ID': identifier, 'OriginalPaperDOI': original, 'RetractionDOI': notice,
            'RetractionNature': 'Retraction', 'OriginalPaperDate': '1/1/2010',
            'RetractionDate': '1/1/2020', 'Reason': 'Error;Investigation;', **extra}


class SnapshotAnalysisTests(unittest.TestCase):
    def normalize(self, rows):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'rw.csv'
            keys = sorted(set().union(*(row.keys() for row in rows)))
            with source.open('w', newline='') as output:
                writer = csv.DictWriter(output, fieldnames=keys)
                writer.writeheader()
                writer.writerows(rows)
            return canonicalize_rw(source, '2026-09-10')

    def test_same_original_multiple_notices_and_reason_union(self):
        papers, notices, roles, accounting = self.normalize([
            source_row('1'), source_row('2', notice='10.1234/second', RetractionDate='1/1/2021', Reason='New reason;')])
        self.assertEqual(len(papers), 1)
        self.assertEqual(len(notices), 2)
        self.assertEqual(papers[0]['retracted'], '2020-01-01')
        self.assertEqual(papers[0]['rw_ids'], ['1', '2'])
        self.assertEqual(papers[0]['reasons'], ['Error', 'Investigation', 'New reason'])

    def test_bulk_notice_does_not_merge_originals(self):
        papers, notices, roles, accounting = self.normalize([source_row('1'), source_row('2', original='10.1234/another')])
        self.assertEqual(len(papers), 2)
        self.assertEqual(len(notices), 1)
        self.assertEqual(len(notices[0]['original_ids']), 2)

    def test_other_categories_supply_role_evidence_not_population_b(self):
        papers, notices, roles, accounting = self.normalize([source_row('1', RetractionNature='Correction')])
        self.assertEqual(papers, [])
        self.assertIn(('doi', '10.1234/notice', 'notice'), roles)
        self.assertEqual(len(notices), 1)

    def test_duplicate_doi_is_ambiguous_not_smallest_id(self):
        paper = {'doi': '10.1234/original', 'pmids': []}
        match = select_match(paper, {'10.1234/original': {'W1', 'W2'}}, {})
        self.assertEqual(match['match_outcome'], 'ambiguous')
        self.assertIsNone(match['selected_id'])

    def test_contradictory_identifiers_block_selection(self):
        match = select_match({'doi': '10.1234/original', 'pmids': ['1']}, {'10.1234/original': {'W1'}}, {'1': {'W2'}})
        self.assertEqual(match['match_outcome'], 'conflicting')
        self.assertIsNone(match['selected_id'])

    def test_match_has_no_flag_restriction_and_no_survivor_guess(self):
        match = select_match({'doi': '10.1234/original', 'pmids': []}, {'10.1234/original': {'W1'}}, {})
        self.assertEqual(match['selected_id'], 'W1')
        absent = select_match({'doi': '10.1234/missing', 'pmids': []}, {}, {})
        self.assertEqual(absent['oa_record_state'], 'absent')
        self.assertIsNone(absent['selected_id'])

    def test_country_modes_and_incomplete_affiliations(self):
        authorships = [
            {'author': {'id': 'https://openalex.org/A1'}, 'countries': ['CN'], 'institutions': [{'id': 'https://openalex.org/I1', 'country_code': 'CN'}]},
            {'author': {'id': 'https://openalex.org/A2'}, 'countries': ['CN', 'US'], 'institutions': [{'id': 'https://openalex.org/I1', 'country_code': 'CN'}]},
            {'author': {}, 'countries': [], 'institutions': []},
        ]
        modes, authors, institutions = country_sets({'authorships': authorships, 'authors_count': 4})
        self.assertEqual(modes['institution_country']['countries'], ['CN'])
        self.assertEqual(modes['authorship_country']['countries'], ['CN', 'US'])
        self.assertEqual(modes['institution_country']['collaboration'], 'single_country_incomplete')
        self.assertEqual(modes['authorship_country']['collaboration'], 'multi_country_observed')
        counts, weights, summary = associations({'W1': ['CN', 'CN', 'US']})
        self.assertEqual(dict(counts), {'CN': 1, 'US': 1})
        self.assertEqual(weights['CN'], .5)
        self.assertEqual(weights['US'], .5)
        self.assertEqual(weights['CN'], .5)

    def test_entity_associations_and_unique_union_differ(self):
        counts, weights, summary = associations({'W1': ['A1', 'A2']})
        self.assertEqual(summary['association_total'], 2)
        self.assertEqual(summary['top_k_union_works'], 1)
        self.assertEqual(summary['gini'], 0)

    def test_zero_denominator_differs_from_zero_numerator(self):
        self.assertIsNone(cohort_rate(0, 0)['value'])
        self.assertEqual(cohort_rate(0, 1000)['value'], 0)
        self.assertFalse(cohort_rate(0, 1000)['ranking_eligible'])
        self.assertTrue(cohort_rate(20, 1000)['ranking_eligible'])

    def test_invalid_and_negative_dates_are_preserved_as_exclusions(self):
        papers, notices, roles, accounting = self.normalize([source_row('1', OriginalPaperDate='1/1/2022')])
        self.assertTrue(papers[0]['negative_lag'])
        self.assertIsNone(papers[0]['lag_days'])
        self.assertEqual(papers[0]['raw_dates'][0]['publication'], '1/1/2022')

    def test_pmid_has_its_own_namespace(self):
        self.assertEqual(pmid('https://pubmed.ncbi.nlm.nih.gov/0123/'), '123')
        self.assertIsNone(pmid('Unavailable'))
        self.assertIsNone(pmid('0'))

    def test_manifest_to_aggregate_report_with_notice_and_false_flag_match(self):
        from test_validate_snapshot import SnapshotValidationTests
        fixture = SnapshotValidationTests()
        fixture.setUp()
        self.addCleanup(fixture.temporary.cleanup)
        table = fixture.table
        table = table.set_column(table.schema.get_field_index('doi'), 'doi', pa.array(['10.1234/notice', '10.1234/original', '10.1234/third']))
        table = table.set_column(table.schema.get_field_index('is_xpac'), 'is_xpac', pa.array([False, False, True]))
        table = table.set_column(table.schema.get_field_index('is_retracted'), 'is_retracted', pa.array([True, False, True]))
        table = table.append_column('title', pa.array(['Retraction notice', 'Original article', 'Expansion work']))
        table = table.append_column('authors_count', pa.array([0, 0, 0], type=pa.int32()))
        table = table.append_column('topics', pa.array([[], [], []], type=pa.list_(table.schema.field('primary_topic').type)))
        source = pa.struct([('id', pa.string()), ('display_name', pa.string()), ('type', pa.string())])
        table = table.append_column('primary_location', pa.array([None] * 3, type=pa.struct([('source', source)])))
        table = table.append_column('cited_by_count', pa.array([0, 3, None], type=pa.int32()))
        table = table.append_column('referenced_works', pa.array([['https://openalex.org/W2'], [], []], type=pa.list_(pa.string())))
        table = table.append_column('language', pa.array(['en', 'en', None], type=pa.string()))
        table = table.append_column('open_access', pa.array([{'oa_status': 'closed'}]*3, type=pa.struct([('oa_status', pa.string())])))
        author = pa.struct([('author', pa.struct([('id', pa.string())])), ('countries', pa.list_(pa.string())),
            ('institutions', pa.list_(pa.struct([('id', pa.string()), ('display_name', pa.string()), ('country_code', pa.string())])))])
        table = table.set_column(table.schema.get_field_index('authorships'), 'authorships', pa.array([[], [], []], type=pa.list_(author)))
        pq.write_table(table, fixture.work)
        size = fixture.work.stat().st_size
        fixture.manifest['entities'][0]['files'][0]['meta']['content_length'] = size
        fixture.manifest['entities'][0]['content_length'] = size
        fixture.manifest['meta']['content_length'] = size
        atomic_json(fixture.root / 'manifest.json', fixture.manifest)
        response = MagicMock()
        response.__enter__.return_value.read.return_value = (fixture.root / 'manifest.json').read_bytes()
        with patch('urllib.request.urlopen', return_value=response):
            validation = validate(fixture.root, fixture.output, scan_ids=True, check_remote=True, accept_retrospective=True)
        self.assertEqual(validation['status'], 'validated')
        rw_csv = fixture.root.parent / 'rw.csv'
        row = source_row('1')
        with rw_csv.open('w', newline='') as output:
            writer = csv.DictWriter(output, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
        rw_meta = fixture.root.parent / 'rw.json'
        atomic_json(rw_meta, {'rw_source_commit': 'test-commit', 'rw_snapshot_date': '2026-09-10', 'rw_csv_sha256': digest(rw_csv.read_bytes())})
        run = scan_snapshot(Path(validation['output_dir']) / 'validation.json', rw_csv, rw_meta,
                            fixture.root.parent / 'analysis', memory_limit='512MB', threads=1, workers=1)
        dimension_scan(run, workers=1, threads=1, memory_limit='512MB')
        report = build(run)
        citation_scan(run, workers=1, threads=1, memory_limit='512MB')
        with patch('pipeline.snapshot_citations.scan_file', side_effect=AssertionError('Completed edge shards must be reused')):
            citation_scan(run, workers=1, threads=1, memory_limit='512MB')
        supplement_scan(run, workers=1, threads=1, memory_limit='512MB')
        report = build(run)
        updated_manifest = json.loads((report / 'manifest.json').read_text())
        self.assertTrue(updated_manifest['capabilities']['incoming_citations'])
        self.assertTrue(updated_manifest['capabilities']['fixed_publication_followup'])
        overview = json.loads((report / 'overview.json').read_text())
        populations = {row['id']: row['value'] for row in overview['charts'][0]['rows']}
        self.assertEqual(populations['A0'], 1)
        self.assertEqual(populations['A1'], 0)
        self.assertEqual(populations['C'], 1)
        self.assertEqual(populations['D'], 1)
        quality = json.loads((report / 'quality.json').read_text())
        reconciliation = {row['id']: row['value'] for row in quality['charts'][0]['rows']}
        self.assertEqual(reconciliation['matched_flag_false'], 1)
        matched = json.loads((run / 'rw_oa_match.json').read_text())
        self.assertEqual(matched['doi:10.1234/original']['selected_id'], 'https://openalex.org/W2')
        public = fixture.root.parent / 'public'
        (public / 'data').mkdir(parents=True)
        repository = Path(__file__).resolve().parents[1]
        for name in ('report.json', 'samples.json'):
            shutil.copy2(repository / 'public/data' / name, public / 'data' / name)
        publish(report, public)
        publish(report, public)
        original_manifest = (public / 'data/snapshot/manifest.json').read_bytes()
        manifest = json.loads((report / 'manifest.json').read_text())
        manifest['status'] = 'not_computed'
        atomic_json(report / 'manifest.json', manifest)
        with self.assertRaises(subprocess.CalledProcessError):
            publish(report, public)
        self.assertEqual((public / 'data/snapshot/manifest.json').read_bytes(), original_manifest)


if __name__ == '__main__':
    unittest.main()
