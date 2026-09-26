import json
from pathlib import Path
import tempfile
import unittest

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from disruption.src import research_views as research
from disruption.src.window_results import digest_file
from disruption.src import window_results as windows
from disruption.tests.test_bulk_results import source_fixture
from disruption.tests.test_window_results import SNAPSHOT


def rows_fixture():
    base = {"work_id": "https://openalex.org/W1", "publication_year": 2020,
            "window": "5y", "window_policy": "exclude_publication_year", "is_mature": True,
            "computation_status": "complete", "citation_count": 12, "reference_count_valid": 12,
            "reference_list_unknown": False, "has_valid_publication_year": True,
            "citation_count_consistent": True, "incoming_earlier_year_count": 0,
            "incoming_unknown_year_count": 0, "disruption_cd": 0.25,
            "NF": 5, "NB": 3, "NR": 0, "future_related_count": 8,
            "disruption_cd_raw_observed": 0.25, "disruption_no_nr_raw_observed": 0.25,
            "disruption_no_nr": 0.25, "flags": ["fixture"],
            "source_record_json": json.dumps({"reference_quality_counts": {
                "invalid": 0, "dangling": 0, "self_loop": 0, "duplicate": 2}})}
    return [base,
            {**base, "work_id": "https://openalex.org/W2", "is_mature": False, "disruption_cd": None},
            {**base, "work_id": "https://openalex.org/W3", "window": "lifetime", "is_mature": None},
            {**base, "work_id": "https://openalex.org/W4", "publication_year": None,
             "has_valid_publication_year": False, "reference_count_valid": None, "citation_count": None,
             "computation_status": "unobservable", "disruption_cd": None},
            {**base, "work_id": "https://openalex.org/W5", "source_record_json": json.dumps({
                "reference_quality_counts": {"invalid": 1, "dangling": 0, "self_loop": 0}}),
             "incoming_unknown_year_count": 1},
            {**base, "work_id": "https://openalex.org/W6", "source_record_json": "{}",
             "incoming_unknown_year_count": None},
            {**base, "work_id": "https://openalex.org/W7", "reference_list_unknown": True}]


class ResearchViewTests(unittest.TestCase):
    def test_sql_nulls_maturity_lifetime_and_no_filtering(self):
        connection = duckdb.connect()
        rows = rows_fixture()
        connection.register("test_records", pa.Table.from_pylist(rows))
        sql = research.render_sql("CREATE VIEW disruption_research AS SELECT * FROM test_records;\n",
                                  "2026-06-26", "disruption-v1", "bulk-windows-v1")
        connection.execute(sql)
        actual = connection.execute("SELECT work_id, has_ref_10, has_citation_10, eligible_r10_c10, has_valid_reference_graph, has_valid_citation_graph, paper_age_at_snapshot FROM disruption_research_ready ORDER BY work_id").fetchall()
        self.assertEqual(len(actual), len(rows))
        self.assertEqual(actual[0][1:], (True, True, True, True, True, 6))
        self.assertEqual(connection.execute("SELECT complete_calendar_years_exclude_publication_year, complete_calendar_years_include_publication_year FROM disruption_research_ready WHERE work_id = 'https://openalex.org/W1'").fetchone(), (5, 6))
        self.assertEqual(connection.execute("SELECT count(*) FROM disruption_work_wide").fetchone()[0], len(rows))
        self.assertEqual(connection.execute("SELECT future_citation_count_lifetime_exclude_publication_year FROM disruption_work_wide WHERE work_id = 'https://openalex.org/W3'").fetchone()[0], 12)
        self.assertEqual(actual[1][2:4], (None, None))
        self.assertEqual(actual[2][2:4], (True, True))
        self.assertEqual(actual[3][1:], (None, None, None, None, None, None))
        self.assertEqual(actual[4][4:6], (False, False))
        self.assertEqual(actual[5][4:6], (None, None))
        self.assertIsNone(actual[6][4])
        self.assertEqual(connection.execute("SELECT disruption_cd FROM disruption_research_ready ORDER BY work_id").fetchall(),
                         [(row["disruption_cd"],) for row in rows])
        connection.execute("CREATE TABLE matched_retraction_works AS SELECT * FROM (VALUES ('https://openalex.org/W1'), ('https://openalex.org/W1'), ('https://openalex.org/W99')) identifiers(work_id)")
        joined = connection.execute(research.RETRACTION_SQL).fetchall()
        self.assertEqual(len(joined), 2)
        self.assertTrue(any(row[0] == "https://openalex.org/W99" and all(value is None for value in row[1:]) for row in joined))
        connection.close()

    def test_custom_ranges_sparse_coverage_and_wide_both_policies(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, records = source_fixture(root)
            windows.materialize(source, root / "partition")
            connection = duckdb.connect()
            for name in ("focal", "annual", "windows"):
                connection.execute(f"CREATE VIEW disruption_{name} AS SELECT * FROM read_parquet({research.literal(root / 'partition' / (name + '.parquet'))})")
            connection.execute(research.render_custom_windows(SNAPSHOT))
            for first_age, last_age, expected in ((1, 4, (2, 1, 1)), (1, 7, (2, 2, 2)), (2, 5, (1, 2, 1))):
                actual = connection.execute(f"SELECT NF, NB, NR FROM disruption_age_range({first_age}, {last_age}) WHERE work_id = 'https://openalex.org/W1'").fetchone()
                self.assertEqual(actual, expected)
            self.assertEqual(connection.execute("SELECT NF, NB, NR FROM disruption_age_range(7, 7) WHERE work_id = 'https://openalex.org/W1'").fetchone(), (None, None, None))
            self.assertEqual(connection.execute("SELECT NF, NB, NR FROM disruption_age_range(1, 4) WHERE work_id = 'https://openalex.org/W6'").fetchone(), (None, None, None))
            self.assertEqual(connection.execute("SELECT NF, NB, NR FROM disruption_age_range(1, 1) WHERE work_id = 'https://openalex.org/W1'").fetchone(), (1, 0, 0))
            self.assertEqual(connection.execute("SELECT is_mature, disruption_cd FROM disruption_age_range(1, 7) WHERE work_id = 'https://openalex.org/W1'").fetchone(), (False, None))
            connection.execute("CREATE VIEW disruption_research AS SELECT metrics.*, focal.publication_year, focal.reference_count_valid, focal.source_record_json, focal.reference_list_unknown, focal.incoming_earlier_year_count, focal.incoming_unknown_year_count, focal.publication_year BETWEEN 1 AND 9999 AS has_valid_publication_year FROM disruption_windows metrics JOIN disruption_focal focal USING (work_id)")
            connection.execute(research.render_sql("", SNAPSHOT, "disruption-v1", "bulk-windows-v1"))
            self.assertEqual(connection.execute("SELECT count(*) FROM disruption_work_wide").fetchone()[0], len(records))
            self.assertEqual(connection.execute("SELECT future_citation_count_lifetime_exclude_publication_year, future_citation_count_lifetime_include_publication_year FROM disruption_work_wide WHERE work_id = 'https://openalex.org/W1'").fetchone(), (4, 5))
            self.assertEqual(connection.execute("SELECT future_citation_count_lifetime_exclude_publication_year, future_citation_count_lifetime_include_publication_year FROM disruption_work_wide WHERE work_id = 'https://openalex.org/W6'").fetchone(), (None, None))
            connection.execute("CREATE TABLE focal_copy AS SELECT * FROM disruption_focal")
            connection.execute("CREATE OR REPLACE VIEW disruption_focal AS SELECT * FROM focal_copy UNION ALL SELECT * REPLACE ('https://openalex.org/W77' AS work_id) FROM focal_copy WHERE work_id = 'https://openalex.org/W1' UNION ALL SELECT * REPLACE ('https://openalex.org/W78' AS work_id, 'incomplete' AS computation_status, false AS sparse_zero_coverage_complete) FROM focal_copy WHERE work_id = 'https://openalex.org/W1'")
            self.assertEqual(connection.execute("SELECT NF, NB, NR FROM disruption_age_range(1, 4) WHERE work_id = 'https://openalex.org/W77'").fetchone(), (0, 0, 0))
            self.assertEqual(connection.execute("SELECT NF, NB, NR FROM disruption_age_range(1, 4) WHERE work_id = 'https://openalex.org/W78'").fetchone(), (None, None, None))
            connection.close()

    def test_atomic_sidecar_and_provenance_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            foundation = root / "run.json"
            foundation.write_text(json.dumps({"status": "complete", "rows": 7, "config_sha256": "foundation-hash",
                                             "configuration": {"snapshot_date": "2026-06-26"}}))
            graph = root / "graph.json"
            graph.write_text(json.dumps({"status": "complete", "node_count": 7,
                                        "foundation_config_sha256": "foundation-hash", "snapshot_date": "2026-06-26"}))
            pq.write_table(pa.Table.from_pylist(rows_fixture()), root / "fixture.parquet")
            (root / "views.sql").write_text(f"CREATE VIEW disruption_research AS SELECT * FROM read_parquet({research.literal(root / 'fixture.parquet')});\n")
            source = {"complete": True, "scope": "all_graph_works", "focal_rows": 7, "window_rows": 56,
                      "schema_version": "disruption-v1", "calculation_version": "bulk-windows-v1",
                      "views_sha256": digest_file(root / "views.sql"),
                      "config": {"foundation": {"path": str(root), "run_sha256": digest_file(foundation)}},
                      "source_provenance": {"openalex_snapshot_date": "2026-06-26", "graph_manifest_sha256": digest_file(graph)}}
            analytical = root / "analytics.json"
            analytical.write_text(json.dumps(source))
            result = research.generate(analytical, foundation, graph, root / "research")
            self.assertTrue(result["complete"])
            for filename, metadata in result["outputs"].items():
                self.assertEqual(digest_file(root / "research" / filename), metadata["sha256"])
            connection = duckdb.connect()
            connection.execute((root / "research/research_views.sql").read_text())
            self.assertEqual(connection.execute("SELECT count(*) FROM disruption_research_ready").fetchone()[0], 7)
            connection.close()
            with self.assertRaises(FileExistsError):
                research.generate(analytical, foundation, graph, root / "research")
            graph.write_text(graph.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "graph provenance"):
                research.generate(analytical, foundation, graph, root / "bad-research")
            self.assertFalse((root / "bad-research").exists())


if __name__ == "__main__":
    unittest.main()
