import copy
from datetime import date
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import pyarrow.parquet as pq

from disruption.reference.oracle import ReferenceGraph
from disruption.reference.test_oracle import fixture, record
from disruption.src import window_results as windows


SNAPSHOT = "2026-06-26"


def annual_record(graph, identifier):
    annual = graph.annual(identifier)
    annual["graph_node_index"] = list(graph.works).index(annual["work_id"])
    if annual["computation_status"] == "complete":
        annual["observed_age_start"] = 0
        annual["observed_age_end"] = graph.snapshot_date.year - annual["publication_year"]
    else:
        annual["computation_status"] = "unavailable_publication_year"
    annual["annual_counts"] = [row for row in annual["annual_counts"] if any(row[name] for name in windows.COUNTS)]
    return annual


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.graph = ReferenceGraph(fixture(), SNAPSHOT)
        self.annual = annual_record(self.graph, "W1")

    def test_both_policies_match_oracle(self):
        for policy in windows.POLICIES:
            for years in (1, 2, 3, 5, 7, 10, 15, "lifetime"):
                with self.subTest(policy=policy, years=years):
                    expected = self.graph.window(self.annual, policy, years)
                    actual = windows.window_result(self.annual, policy, years, SNAPSHOT)
                    self.assertEqual(expected, actual)
        self.assertEqual(windows.window_result(self.annual, windows.POLICIES[0], 5, SNAPSHOT)["planned_end_date"], "2025-12-31")
        self.assertEqual(windows.window_result(self.annual, windows.POLICIES[1], 5, SNAPSHOT)["planned_end_date"], "2024-12-31")

    def test_immature_and_lifetime(self):
        immature = windows.window_result(self.annual, windows.POLICIES[0], 10, SNAPSHOT)
        self.assertFalse(immature["is_mature"])
        self.assertIsNone(immature["disruption_cd"])
        self.assertIsNotNone(immature["disruption_cd_raw_observed"])
        lifetime = windows.window_result(self.annual, windows.POLICIES[0], "lifetime", SNAPSHOT)
        self.assertIsNone(lifetime["is_mature"])
        self.assertTrue(lifetime["snapshot_limited"])
        self.assertIsNotNone(lifetime["disruption_cd"])

    def test_unknown_and_uncomputed_are_not_zero(self):
        unknown = annual_record(self.graph, "W6")
        windows.validate_record(unknown, date.fromisoformat(SNAPSHOT))
        result = windows.window_result(unknown, windows.POLICIES[0], 5, SNAPSHOT)
        self.assertIsNone(result["NF"])
        incomplete = {**self.annual, "computation_status": "incomplete", "annual_counts": []}
        self.assertIsNone(windows.window_result(incomplete, windows.POLICIES[0], 5, SNAPSHOT)["NF"])
        with self.assertRaises(ValueError):
            windows.validate_record(incomplete, date.fromisoformat(SNAPSHOT))

    def test_no_references_raw_one_and_empty_window(self):
        graph = ReferenceGraph([record(1, 2020), record(2, 2021, [1])], SNAPSHOT)
        annual = annual_record(graph, "W1")
        result = windows.window_result(annual, windows.POLICIES[0], 5, SNAPSHOT)
        self.assertEqual(result["disruption_cd_raw_observed"], 1)
        self.assertIsNone(result["disruption_cd"])
        self.assertIn("no_references", result["flags"])
        graph = ReferenceGraph([record(1, 2026)], SNAPSHOT)
        result = windows.window_result(annual_record(graph, "W1"), windows.POLICIES[0], 3, SNAPSHOT)
        self.assertIsNone(result["NF"])
        self.assertIsNone(result["observed_end_date"])

    def test_warning_preserves_independent_counts(self):
        annual = copy.deepcopy(self.annual)
        annual["annual_counts"][1]["citation_count"] += 1
        result = windows.window_result(annual, windows.POLICIES[0], 5, SNAPSHOT)
        self.assertEqual(result["citation_partition_delta"], 1)
        self.assertEqual(result["citation_count"], 5)
        self.assertEqual(result["disruption_cd"], 0)
        self.assertIn("citation_partition_warning", result["flags"])

    def test_partial_year_and_sparse_coverage_validation(self):
        windows.validate_record(self.annual, date.fromisoformat(SNAPSHOT))
        for mutation in ("coverage", "partial", "duplicate", "negative"):
            annual = copy.deepcopy(self.annual)
            if mutation == "coverage":
                del annual["observed_age_end"]
            elif mutation == "partial":
                annual["annual_counts"][-1]["is_partial_calendar_year"] = False
            elif mutation == "duplicate":
                annual["annual_counts"].append(annual["annual_counts"][-1])
            else:
                annual["annual_counts"][0]["NF"] = -1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                windows.validate_record(annual, date.fromisoformat(SNAPSHOT))

    def test_only_nr_cd_zero_no_nr_undefined(self):
        graph = ReferenceGraph([record(1, 2020, [2]), record(2, 2019), record(3, 2021, [2])], SNAPSHOT)
        result = windows.window_result(annual_record(graph, "W1"), windows.POLICIES[0], 5, SNAPSHOT)
        self.assertEqual(result["disruption_cd"], 0)
        self.assertIsNone(result["disruption_no_nr"])
        self.assertIn("no_future_citations", result["flags"])


class MaterializationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        graph = ReferenceGraph(fixture(), SNAPSHOT)
        self.records = [annual_record(graph, f"W{number}") for number in (1, 6)]
        self.source = self.root / "annual.jsonl.gz"
        self.manifest = self.root / "manifest.json"
        self.write_source()

    def tearDown(self):
        self.temporary.cleanup()

    def write_source(self):
        with gzip.open(self.source, "wt") as stream:
            for record_value in self.records:
                stream.write(json.dumps(record_value) + "\n")
        self.metadata = {"complete": True, "schema_version": "disruption-annual-v1",
                         "openalex_snapshot_date": SNAPSHOT, "config_sha256": "fixture",
                         "sparse_zero_semantics": "complete_observable_bins",
                         "partitions": [{"file": self.source.name, "sha256": windows.digest_file(self.source),
                                         "rows": len(self.records)}]}
        self.manifest.write_text(json.dumps(self.metadata))

    def test_streaming_three_compressed_tables_and_immutable_output(self):
        destination = self.root / "output"
        result = windows.materialize(self.manifest, destination, batch_rows=1)
        self.assertEqual(result["outputs"]["focal"]["rows"], 2)
        self.assertEqual(result["outputs"]["windows"]["rows"], 16)
        for name in ("focal", "annual", "windows"):
            parquet = pq.ParquetFile(destination / f"{name}.parquet")
            self.assertEqual(parquet.metadata.row_group(0).column(0).compression, "ZSTD")
        focal = pq.read_table(destination / "focal.parquet").to_pylist()
        self.assertTrue(focal[0]["sparse_zero_coverage_complete"])
        self.assertFalse(focal[1]["sparse_zero_coverage_complete"])
        self.assertEqual(json.loads(focal[0]["source_record_json"])["reference_quality_counts"]["duplicate"], 1)
        with self.assertRaises(FileExistsError):
            windows.materialize(self.manifest, destination)

    def test_corrupted_partition_rejected(self):
        self.source.write_bytes(self.source.read_bytes() + b"corruption")
        with self.assertRaisesRegex(ValueError, "checksum"):
            windows.materialize(self.manifest, self.root / "output")
        self.assertFalse((self.root / "output").exists())

    def test_source_order_does_not_require_sorted_work_ids(self):
        self.records[0]["work_id"] = "https://openalex.org/W900"
        self.records[1]["work_id"] = "https://openalex.org/W2"
        self.write_source()
        result = windows.materialize(self.manifest, self.root / "output")
        self.assertEqual(result["outputs"]["focal"]["rows"], 2)

    def test_incomplete_manifest_or_missing_coverage_rejected(self):
        for field in ("complete", "sparse_zero_semantics"):
            metadata = {**self.metadata, field: None}
            self.manifest.write_text(json.dumps(metadata))
            with self.assertRaises(ValueError):
                windows.materialize(self.manifest, self.root / "output")

    def test_duplicate_focal_and_incorrect_rows_are_atomic_failures(self):
        self.records.append(self.records[-1])
        self.write_source()
        with self.assertRaisesRegex(ValueError, "unique"):
            windows.materialize(self.manifest, self.root / "output")
        self.assertFalse((self.root / "output").exists())
        self.records.pop()
        self.write_source()
        self.metadata["partitions"][0]["rows"] += 1
        self.manifest.write_text(json.dumps(self.metadata))
        with self.assertRaisesRegex(ValueError, "row count"):
            windows.materialize(self.manifest, self.root / "output")
        self.assertFalse((self.root / "output").exists())


if __name__ == "__main__":
    unittest.main()
