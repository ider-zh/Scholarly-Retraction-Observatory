import csv
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pyarrow.parquet as pq

from pipeline.broad_snapshot import derive
from pipeline.snapshot import scan_snapshot
from pipeline.snapshot_report import build
from pipeline.snapshot_dimensions import run as dimensions
from pipeline.snapshot_taxonomy import run as taxonomy
from pipeline.snapshot_citations import run as citations
from pipeline.snapshot_concepts import run as concepts
from pipeline.snapshot_supplement import run as supplement
from pipeline.validate_snapshot import atomic_json, digest, validate


class BroadPipelineTests(unittest.TestCase):
    def test_nonarticle_numerator_and_denominators_are_recomputed_together(self):
        from test_validate_snapshot import SnapshotValidationTests
        fixture = SnapshotValidationTests()
        fixture.setUp()
        self.addCleanup(fixture.temporary.cleanup)
        table = fixture.table
        for name, values in {'doi': ['10.1234/uncertain', '10.1234/original', '10.1234/notice'],
                             'type': ['retraction', 'review', 'article'],
                             'is_xpac': [False] * 3, 'is_retracted': [True, False, True]}.items():
            table = table.set_column(table.schema.get_field_index(name), name, pa.array(values))
        table = table.append_column('title', pa.array(['Retraction Note: uncertain', 'RETRACTED ARTICLE: review', 'Notice']))
        table = table.append_column('authors_count', pa.array([0] * 3))
        table = table.append_column('topics', pa.array([[]] * 3, type=pa.list_(table.schema.field('primary_topic').type)))
        concept = pa.struct([('id', pa.string()), ('display_name', pa.string()), ('level', pa.int32()), ('score', pa.float64())])
        table = table.append_column('concepts', pa.array([[dict(id='https://openalex.org/C1', display_name='Test', level=0, score=0.0)]] * 3, type=pa.list_(concept)))
        source = pa.struct([('id', pa.string()), ('display_name', pa.string()), ('type', pa.string())])
        table = table.append_column('primary_location', pa.array([None] * 3, type=pa.struct([('source', source)])))
        table = table.append_column('cited_by_count', pa.array([0] * 3))
        table = table.append_column('referenced_works', pa.array([['https://openalex.org/W2'], [], []], type=pa.list_(pa.string())))
        table = table.append_column('language', pa.array(['en'] * 3))
        table = table.append_column('open_access', pa.array([{'oa_status': 'closed'}] * 3))
        institution = pa.struct([('id', pa.string()), ('display_name', pa.string()), ('country_code', pa.string())])
        authorship = pa.struct([('author', pa.struct([('id', pa.string()), ('display_name', pa.string())])), ('countries', pa.list_(pa.string())), ('institutions', pa.list_(institution))])
        table = table.set_column(table.schema.get_field_index('authorships'), 'authorships', pa.array([[]] * 3, type=pa.list_(authorship)))
        pq.write_table(table, fixture.work)
        size = fixture.work.stat().st_size
        fixture.manifest['entities'][0]['files'][0]['meta']['content_length'] = size
        fixture.manifest['entities'][0]['content_length'] = size
        fixture.manifest['meta']['content_length'] = size
        atomic_json(fixture.root / 'manifest.json', fixture.manifest)
        response = MagicMock()
        response.__enter__.return_value.read.return_value = (fixture.root / 'manifest.json').read_bytes()
        with patch('urllib.request.urlopen', return_value=response):
            validated = validate(fixture.root, fixture.output, scan_ids=True, check_remote=True, accept_retrospective=True)
        root = fixture.root.parent
        source_csv = root / 'rw.csv'
        record = {'Record ID': '1', 'OriginalPaperDOI': '10.1234/original', 'RetractionDOI': '10.1234/notice', 'RetractionNature': 'Retraction', 'OriginalPaperDate': '1/1/2020', 'RetractionDate': '1/1/2021'}
        with source_csv.open('w', newline='') as output:
            writer = csv.DictWriter(output, fieldnames=list(record))
            writer.writeheader()
            writer.writerow(record)
        atomic_json(root / 'rw.json', {'rw_source_commit': 'test', 'rw_snapshot_date': '2026-09-10', 'rw_csv_sha256': digest(source_csv.read_bytes())})
        legacy = scan_snapshot(Path(validated['output_dir']) / 'validation.json', source_csv, root / 'rw.json', root / 'legacy', workers=1, threads=1, memory_limit='512MB')
        broad = derive(legacy, root / 'broad', workers=1)
        options = dict(workers=1, threads=1, memory_limit='512MB')
        dimensions(broad, **options)
        build(broad)
        for scan in (citations, concepts, taxonomy, supplement):
            scan(broad, **options)
        report = build(broad)
        overview = json.loads((report / 'overview.json').read_text())
        counts = {row['id']: row['value'] for row in overview['charts'][0]['rows']}
        self.assertEqual((counts['A0'], counts['A1'], counts['D']), (2, 1, 2))
        annual = json.loads((report / 'time.json').read_text())['charts']
        rate = next(chart for chart in annual if chart['slice_id'] == 'A1_over_D-all')
        self.assertEqual((rate['rows'][0]['numerator'], rate['rows'][0]['denominator']), (1, 2))
        self.assertNotIn('suspected_notice_denominator', rate['rows'][0])
        for chart in annual:
            if chart['chart_id'] == 'T3' and 'fixed-publication' in chart['slice_id']:
                self.assertEqual(chart['scope']['work_types'], ['all'])
                self.assertEqual(len(chart['rows']), 1)
                self.assertEqual((chart['rows'][0]['numerator'], chart['rows'][0]['denominator']), (1, 2))
        explorer = json.loads((report / 'fields.json').read_text())['discipline_explorer']
        self.assertEqual(explorer['taxonomies'][1]['denominator'][0], 2)
        self.assertEqual(explorer['taxonomies'][1]['counts']['A1'][0], 1)
        self.assertEqual(json.loads((broad / 'citations-complete.json').read_text())['targets'], 1)
