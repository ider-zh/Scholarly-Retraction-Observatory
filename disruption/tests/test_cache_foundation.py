import datetime
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

import pyarrow as pa
import pyarrow.parquet as pq


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "cache_foundation.py"
SPEC = importlib.util.spec_from_file_location("cache_foundation", MODULE_PATH)
cache = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cache)


def fixture_table():
    classification = pa.struct([("id", pa.string()), ("display_name", pa.string())])
    topic = pa.struct([("id", pa.string()), ("display_name", pa.string()),
                       ("subfield", classification), ("field", classification), ("domain", classification)])
    location = pa.struct([("source", pa.struct([("id", pa.string()), ("type", pa.string())]))])
    schema = pa.schema([("id", pa.string()), ("doi", pa.string()), ("publication_year", pa.int32()),
                        ("publication_date", pa.date32()), ("type", pa.string()),
                        ("is_retracted", pa.bool_()), ("is_xpac", pa.bool_()), ("language", pa.string()),
                        ("primary_topic", topic), ("primary_location", location),
                        ("cited_by_count", pa.int32()), ("referenced_works", pa.list_(pa.string()))])
    return pa.Table.from_pylist([
        {"id": "https://openalex.org/W123", "publication_year": 2020,
         "publication_date": datetime.date(2021, 1, 1), "type": "book", "is_xpac": True,
         "referenced_works": ["https://openalex.org/W1", "https://openalex.org/W1", None, "bad-id"],
         "primary_topic": {"id": "https://openalex.org/T1", "display_name": "Topic"}},
        {"id": "bad-work-id", "referenced_works": None},
        {"id": "https://openalex.org/W456", "publication_year": 2028,
         "publication_date": datetime.date(2028, 1, 1), "referenced_works": []}
    ], schema=schema)


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.source = self.root / "source.parquet"
        pq.write_table(fixture_table(), self.source)
        self.task = {"path": str(self.source), "destination": str(self.root / "output"),
                     "relative_path": "works/source.parquet", "identity": cache.source_identity(self.source),
                     "expected_rows": 3, "config_sha256": "fixture", "snapshot_date": "2026-06-26",
                     "batch_rows": 2, "compression_level": 1, "worker_memory_gib": 1,
                     "initial_free": 0, "minimum_free": 0, "maximum_extra": 4 * 10**12}

    def tearDown(self):
        self.directory.cleanup()

    def test_projection_preserves_unknowns_duplicates_and_all_types(self):
        result = cache.build_shard(self.task)
        self.assertEqual(result["rows"], 3)
        self.assertEqual(result["raw_reference_entries"], 4)
        self.assertEqual(result["unknown_reference_lists"], 1)
        nodes = pq.read_table(self.root / "output/nodes.parquet").to_pylist()
        references = pq.read_table(self.root / "output/raw_references.parquet").to_pylist()
        self.assertEqual(nodes[0]["work_id_numeric"], 123)
        self.assertEqual(nodes[0]["work_type"], "book")
        self.assertTrue(nodes[0]["is_xpac"])
        self.assertEqual(nodes[0]["date_quality_flags"], ["date_year_conflict"])
        self.assertEqual(nodes[0]["publication_date_precision"], "unknown")
        self.assertIsNone(nodes[1]["work_id_numeric"])
        self.assertIsNone(nodes[1]["is_xpac"])
        self.assertIsNone(nodes[1]["reference_count_raw"])
        self.assertEqual(nodes[2]["reference_count_raw"], 0)
        self.assertEqual(nodes[2]["date_quality_flags"], ["future_date", "future_year"])
        self.assertEqual(references[0]["referenced_works"], fixture_table().to_pylist()[0]["referenced_works"])
        self.assertIsNone(references[1]["referenced_works"])
        self.assertEqual(references[2]["referenced_works"], [])
        self.assertEqual(pq.ParquetFile(self.root / "output/nodes.parquet").metadata.row_group(0).column(0).compression, "ZSTD")

    def test_resume_checks_checksum_and_source_identity(self):
        cache.build_shard(self.task)
        self.assertTrue(cache.build_shard(self.task)["resumed"])
        with (self.root / "output/nodes.parquet").open("ab") as stream:
            stream.write(b"corrupt")
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            cache.build_shard(self.task)

    def test_source_mutation_blocks_resume(self):
        cache.build_shard(self.task)
        self.source.touch()
        with self.assertRaisesRegex(RuntimeError, "Source changed"):
            cache.build_shard(self.task)

    def test_uncommitted_output_is_rebuilt(self):
        output = self.root / "output"
        output.mkdir()
        (output / "nodes.parquet.partial").write_bytes(b"interrupted")
        (output / "nodes.parquet").write_bytes(b"uncommitted")
        result = cache.build_shard(self.task)
        self.assertEqual(result["rows"], 3)
        self.assertTrue((output / "complete.json").exists())

    def test_zero_rows_keep_output_schema(self):
        pq.write_table(fixture_table().slice(0, 0), self.source)
        self.task.update(identity=cache.source_identity(self.source), expected_rows=0)
        result = cache.build_shard(self.task)
        self.assertEqual(result["rows"], 0)
        self.assertIn("work_id_numeric", pq.read_schema(self.root / "output/nodes.parquet").names)

    def test_row_count_and_disk_guard(self):
        self.task["expected_rows"] = 100
        with self.assertRaisesRegex(ValueError, "row count"):
            cache.build_shard(self.task)
        with self.assertRaisesRegex(RuntimeError, "Disk safety"):
            cache.disk_guard(self.root, 0, 10**30, 4 * 10**12)

    def test_cli_pilot_then_resume_full_and_changed_inventory(self):
        source_root = self.root / "snapshot"
        works = source_root / "works"
        works.mkdir(parents=True)
        entries = []
        for index in range(2):
            path = works / f"part_{index}.parquet"
            pq.write_table(fixture_table(), path)
            entries.append({"url": f"s3://openalex/data/parquet/works/{path.name}",
                            "meta": {"content_length": path.stat().st_size, "record_count": 3}})
        (source_root / "manifest.json").write_text(json.dumps({"date": "2026-06-26", "entities": [{"entity": "works", "files": entries}]}))
        command = [sys.executable, str(MODULE_PATH), "--source", str(source_root),
                   "--output", str(self.root / "cache"), "--workers", "2", "--memory-gib", "2",
                   "--batch-rows", "2", "--min-free-tb", "0", "--allow-small-test-disk"]
        pilot = subprocess.run(command + ["--max-files", "1"], capture_output=True, text=True, timeout=60)
        self.assertEqual(pilot.returncode, 0, pilot.stderr)
        run_root = Path(json.loads(pilot.stdout.splitlines()[-1])["run_root"])
        self.assertEqual(json.loads((run_root / "run.json").read_text())["status"], "pilot_complete")
        complete = subprocess.run(command, capture_output=True, text=True, timeout=60)
        self.assertEqual(complete.returncode, 0, complete.stderr)
        self.assertIn('"resumed": true', complete.stdout)
        metadata = json.loads((run_root / "run.json").read_text())
        self.assertEqual(metadata["status"], "complete")
        self.assertEqual(metadata["rows"], 6)
        (works / "part_1.parquet").touch()
        failed = subprocess.run(command, capture_output=True, text=True, timeout=60)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("Frozen source inventory mismatch", failed.stderr)


if __name__ == "__main__":
    unittest.main()
