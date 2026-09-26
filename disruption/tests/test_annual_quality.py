import json
from pathlib import Path
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq

from disruption.src.annual_quality import audit_all
from disruption.src.window_results import ANNUAL_SCHEMA, digest_file


def published_fixture(root, negative=False):
    directory = root / "published/partitions/part-000000"
    directory.mkdir(parents=True)
    rows = [{"work_id": "https://openalex.org/W1", "age_year": age, "NF": 2, "NB": 1, "NR": 2,
             "citation_count": 3 + delta, "future_related_count": 5 + delta,
             "citation_partition_delta": 0, "citation_count_consistent": True,
             "neighborhood_partition_delta": delta, "neighborhood_count_consistent": False,
             "is_partial_calendar_year": False} for age, delta in ((1, 1), (2, -1))]
    if negative:
        rows[0]["NF"] = -1
    annual = directory / "annual.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=ANNUAL_SCHEMA), annual, compression="zstd")
    outputs = {"annual": {"path": "annual.parquet", "rows": 2, "sha256": digest_file(annual)},
               "focal": {"rows": 1}, "windows": {"rows": 8}}
    partition_manifest = directory / "manifest.json"
    partition_manifest.write_text(json.dumps({"status": "complete", "outputs": outputs}))
    manifest = root / "published/manifest.json"
    manifest.write_text(json.dumps({"complete": True, "scope": "all_graph_works", "focal_rows": 1,
                                    "window_rows": 8, "annual_rows": 2,
                                    "source_provenance": {"complete": True, "scope": "all_graph_works",
                                                          "graph_work_count": 1, "requested_focal_count": 1},
                                    "partitions": [{"index": 0, "path": directory.name, "outputs": outputs,
                                                    "first_node_index": 0, "last_node_index": 0,
                                                    "manifest_sha256": digest_file(partition_manifest)}]}))
    return manifest, annual


class AnnualQualityTests(unittest.TestCase):
    def test_cancelling_deltas_and_misreported_flags_are_warnings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, annual = published_fixture(root)
            original = annual.read_bytes()
            result = audit_all(source, root / "quality", workers=1)
            self.assertTrue(result["complete"])
            self.assertEqual(result["source_manifest_sha256"], digest_file(source))
            self.assertEqual(result["quality_sha256"], digest_file(root / "quality/quality.json"))
            quality = json.loads((root / "quality/quality.json").read_text())
            for prefix in ("citation", "neighborhood"):
                self.assertEqual(quality[prefix]["sum_delta"], 0)
                self.assertEqual(quality[prefix]["mismatched_rows"], 2)
                self.assertEqual(quality[prefix]["minimum_delta"], -1)
                self.assertEqual(quality[prefix]["maximum_delta"], 1)
            self.assertEqual(quality["citation"]["misreported_delta_rows"], 2)
            self.assertEqual(quality["citation"]["misreported_flag_rows"], 2)
            self.assertEqual(quality["neighborhood"]["misreported_delta_rows"], 0)
            self.assertEqual(quality["neighborhood"]["misreported_flag_rows"], 0)
            self.assertEqual(annual.read_bytes(), original)
            with self.assertRaisesRegex(ValueError, "new and outside"):
                audit_all(source, root / "quality", workers=1)

    def test_parallel_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, _ = published_fixture(root)
            result = audit_all(source, root / "quality", workers=2)
            self.assertEqual(result["annual_rows"], 2)

    def test_corruption_and_negative_counts_block_publication(self):
        for negative in (False, True):
            with self.subTest(negative=negative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source, annual = published_fixture(root, negative=negative)
                if not negative:
                    with annual.open("ab") as stream:
                        stream.write(b"corruption")
                with self.assertRaisesRegex(ValueError, "structural|checksum"):
                    audit_all(source, root / "quality", workers=1)
                self.assertFalse((root / "quality").exists())

    def test_reject_incomplete_coverage_and_bad_worker_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, _ = published_fixture(root)
            for workers in (0, 33):
                with self.assertRaisesRegex(ValueError, "Workers"):
                    audit_all(source, root / "quality", workers=workers)
            manifest = json.loads(source.read_text())
            manifest["annual_rows"] = 3
            source.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "coverage"):
                audit_all(source, root / "quality", workers=1)
            manifest["complete"] = False
            source.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "Complete"):
                audit_all(source, root / "quality", workers=1)


if __name__ == "__main__":
    unittest.main()
