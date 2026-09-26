import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from disruption.reference.oracle import ReferenceGraph
from disruption.reference.test_oracle import fixture
from disruption.tests.test_window_results import annual_record, SNAPSHOT
from disruption.src import bulk_results as bulk
from disruption.src import window_results as windows


def source_fixture(root, records=None):
    if records is None:
        graph = ReferenceGraph(fixture(), SNAPSHOT)
        records = [annual_record(graph, identifier) for identifier in graph.works]
    source = root / "annual.jsonl.gz"
    with gzip.open(source, "wt") as stream:
        for record in records:
            stream.write(json.dumps(record) + "\n")
    manifest = {"complete": True, "schema_version": "disruption-annual-v1", "scope": "all_graph_works",
                "openalex_snapshot_date": SNAPSHOT, "sparse_zero_semantics": "complete_observable_bins",
                "graph_work_count": len(records), "requested_focal_count": len(records),
                "partitions": [{"file": source.name, "rows": len(records), "sha256": windows.digest_file(source)}]}
    path = root / "annual-manifest.json"
    path.write_text(json.dumps(manifest))
    return path, records


class BulkTests(unittest.TestCase):
    def test_all_policies_match_oracle_and_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, records = source_fixture(root)
            destination = root / "results"
            result = bulk.materialize_all(source, destination, workers=1, minimum_free_bytes=0)
            self.assertEqual(result["focal_rows"], len(records))
            self.assertEqual(result["window_rows"], len(records) * 8)
            actual = pq.read_table(destination / "partitions/part-000000/windows.parquet").to_pylist()
            expected = [windows.window_result(record, policy, years, SNAPSHOT) for record in records
                        for policy in windows.POLICIES for years in (3, 5, 10, "lifetime")]
            self.assertEqual(actual, expected)
            resumed = bulk.materialize_all(source, destination, workers=1, minimum_free_bytes=0)
            self.assertEqual(result["config_sha256"], resumed["config_sha256"])
            connection = duckdb.connect()
            connection.execute((destination / "views.sql").read_text())
            self.assertEqual(connection.execute("SELECT count(*) FROM disruption_windows").fetchone()[0], len(expected))
            connection.close()
            quality = json.loads((destination / "quality.json").read_text())
            self.assertEqual(sum(row["rows"] for row in quality["computation_status"]), len(expected))
            output = destination / "partitions/part-000000/annual.parquet"
            with output.open("ab") as stream:
                stream.write(b"corruption")
            with self.assertRaisesRegex(ValueError, "checksum"):
                bulk.materialize_all(source, destination, workers=1, minimum_free_bytes=0)

    def test_reject_subset_coverage_and_worker_oversubscription(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, _ = source_fixture(root)
            manifest = json.loads(source.read_text())
            for change in ({"scope": "selected_focals_full_graph_neighborhood"}, {"requested_focal_count": 0}):
                source.write_text(json.dumps({**manifest, **change}))
                with self.assertRaises(ValueError):
                    bulk.materialize_all(source, root / "output", minimum_free_bytes=0)
            with self.assertRaises(ValueError):
                bulk.materialize_all(source, root / "output", workers=41)

    def test_missing_graph_node_is_not_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            graph = ReferenceGraph(fixture(), SNAPSHOT)
            records = [annual_record(graph, identifier) for identifier in graph.works]
            records = copy.deepcopy(records)
            for record in records:
                record["graph_node_index"] += 1
            source, _ = source_fixture(root, records)
            with self.assertRaisesRegex(ValueError, "indices"):
                bulk.materialize_all(source, root / "output", workers=1, minimum_free_bytes=0)
            self.assertFalse((root / "output/manifest.json").exists())

    def test_quality_checks_and_warning_only_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            graph = ReferenceGraph(fixture(), SNAPSHOT)
            record = annual_record(graph, "W1")
            record["annual_counts"][1]["citation_count"] += 1
            source, _ = source_fixture(root, [record])
            windows.materialize(source, root / "partition")
            output = root / "partition/windows.parquet"
            summary = bulk.quality_summary(output, 1)
            self.assertTrue(any(row["value"] == "citation_partition_warning" for row in summary["flags"]))
            rows = pq.read_table(output).to_pylist()
            invalid = next(row for row in rows if row["is_mature"] is False)
            invalid["disruption_cd"] = 0.5
            pq.write_table(pa.Table.from_pylist(rows, schema=windows.WINDOW_SCHEMA), output)
            with self.assertRaisesRegex(ValueError, "invariant"):
                bulk.quality_summary(output, 1)
            invalid["disruption_cd"] = None
            rows[-1] = rows[0]
            pq.write_table(pa.Table.from_pylist(rows, schema=windows.WINDOW_SCHEMA), output)
            with self.assertRaisesRegex(ValueError, "groups"):
                bulk.quality_summary(output, 1)


if __name__ == "__main__":
    unittest.main()
