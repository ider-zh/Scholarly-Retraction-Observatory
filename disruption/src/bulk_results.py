"""Resumable, compressed full-graph analytical exports using the validated window oracle."""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import fcntl
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import shutil

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from disruption.src import window_results as windows


VERSION = "bulk-windows-v1"


def atomic_json(path, value):
    temporary = path.with_suffix(".partial")
    with temporary.open("w") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def sql_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def quality_summary(path, expected_rows):
    connection = duckdb.connect(config={"threads": "1", "memory_limit": "1GiB"})
    try:
        connection.execute("SET temp_directory = ''")
        connection.execute(f"CREATE VIEW window_data AS SELECT * FROM read_parquet({sql_literal(path)})")
        result = {}
        for group in ("computation_status", "is_mature"):
            rows = connection.execute(f'SELECT window_policy, "window", {group}, count(*) FROM window_data GROUP BY ALL').fetchall()
            result[group] = [{"policy": policy, "window": window, "value": value, "rows": count}
                             for policy, window, value, count in rows]
        rows = connection.execute('SELECT window_policy, "window", flag, count(*) FROM (SELECT window_policy, "window", unnest(flags) AS flag FROM window_data) GROUP BY ALL').fetchall()
        result["flags"] = [{"policy": policy, "window": window, "value": flag, "rows": count}
                           for policy, window, flag, count in rows]
        groups = connection.execute('SELECT window_policy, "window", count(*), count(DISTINCT work_id) FROM window_data GROUP BY ALL').fetchall()
        expected_groups = {(policy, window) for policy in windows.POLICIES for window in ("3y", "5y", "10y", "lifetime")}
        if {(policy, window) for policy, window, _, _ in groups} != expected_groups and expected_rows:
            raise ValueError("Missing policy/window groups")
        if any(count != expected_rows or distinct != expected_rows for _, _, count, distinct in groups):
            raise ValueError("Policy/window identity coverage mismatch")
        failures = connection.execute(f"""SELECT count(*) FROM window_data AS metrics
            JOIN read_parquet({sql_literal(path.parent / 'focal.parquet')}) AS focal USING (work_id)
            WHERE NF < 0 OR NB < 0 OR NR < 0 OR citation_count < 0 OR future_related_count < 0
              OR abs(disruption_cd) > 1 OR abs(disruption_no_nr) > 1
              OR abs(disruption_cd_raw_observed) > 1 OR abs(disruption_no_nr_raw_observed) > 1
              OR ((is_mature = false OR focal.reference_count_valid = 0)
                  AND (disruption_cd IS NOT NULL OR disruption_no_nr IS NOT NULL))""").fetchone()[0]
        if failures:
            raise ValueError(f"Window invariant failures: {failures}")
        return result
    finally:
        connection.close()


def export_partition(task):
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    destination = Path(task["destination"])
    if shutil.disk_usage(destination.parent).free < task["minimum_free_bytes"]:
        raise RuntimeError("Minimum disk reserve reached; completed partitions remain resumable")
    if destination.exists():
        result = json.loads((destination / "manifest.json").read_text())
        config = result["config"]
        if (result.get("status") != "complete" or config.get("input_manifest_sha256") != task["source_sha256"]
                or config.get("partition_index") != task["index"]
                or config.get("code_sha256") != task["window_code_sha256"]
                or config.get("compression_level") != task["compression_level"]):
            raise ValueError("Resumed partition definition mismatch")
        for name, metadata in result["outputs"].items():
            path = destination / metadata["path"]
            if windows.digest_file(path) != metadata["sha256"]:
                raise ValueError(f"Resumed {name} checksum mismatch")
            if pq.ParquetFile(path).metadata.num_rows != metadata["rows"]:
                raise ValueError("Resumed Parquet row count mismatch")
    else:
        result = windows.materialize(task["manifest"], destination,
                                     compression_level=task["compression_level"], partition_index=task["index"])
    if result["outputs"]["focal"]["rows"] != task["expected_rows"]:
        raise ValueError("Focal partition coverage mismatch")
    if result["outputs"]["windows"]["rows"] != task["expected_rows"] * 8:
        raise ValueError("Missing policy/window rows")
    source = Path(task["manifest"]).parent / task["source_file"]
    if windows.digest_file(source) != task["source_partition_sha256"]:
        raise ValueError("Source partition changed")
    first_index = last_index = None
    previous = -1
    for batch in pq.ParquetFile(destination / "focal.parquet").iter_batches(columns=["graph_node_index"]):
        for node_index in batch.column(0).to_pylist():
            if node_index <= previous:
                raise ValueError("Focal indices not strictly increasing")
            if first_index is None:
                first_index = node_index
            previous = last_index = node_index
    quality = quality_summary(destination / "windows.parquet", task["expected_rows"])
    atomic_json(destination / "quality.json", quality)
    return {"index": task["index"], "path": destination.name, "outputs": result["outputs"],
            "first_node_index": first_index, "last_node_index": last_index,
            "quality": quality, "manifest_sha256": windows.digest_file(destination / "manifest.json")}


def write_views(destination, foundation):
    parts = destination / "partitions"
    statements = [f"CREATE OR REPLACE VIEW disruption_{name} AS SELECT * FROM read_parquet({sql_literal(parts / '*' / (name + '.parquet'))});"
                  for name in ("focal", "annual", "windows")]
    if foundation:
        statements += [f"CREATE OR REPLACE VIEW disruption_metadata AS SELECT * FROM read_parquet({sql_literal(foundation / 'shards' / '*' / 'nodes.parquet')});",
                       "CREATE OR REPLACE VIEW disruption_research AS SELECT windows.*, focal.* EXCLUDE (work_id), metadata.* EXCLUDE (work_id, work_id_numeric, publication_year, openalex_cited_by_count, reference_count_raw) FROM disruption_windows windows JOIN disruption_focal focal USING (work_id) LEFT JOIN disruption_metadata metadata USING (work_id);"]
    (destination / "views.sql").write_text("\n".join(statements) + "\n")


def materialize_all(manifest_path, destination, workers=32, compression_level=1,
                    foundation=None, minimum_free_bytes=10**12):
    if not 1 <= workers <= 40:
        raise ValueError("Workers must be between 1 and 40")
    manifest_path, destination = Path(manifest_path).resolve(), Path(destination).resolve()
    source = json.loads(manifest_path.read_text())
    if source.get("complete") is not True or source.get("scope") != "all_graph_works":
        raise ValueError("A complete all-graph annual manifest is required")
    expected = source["requested_focal_count"]
    if expected != source["graph_work_count"] or sum(part["rows"] for part in source["partitions"]) != expected:
        raise ValueError("Source focal coverage mismatch")
    if len({part["file"] for part in source["partitions"]}) != len(source["partitions"]):
        raise ValueError("Duplicate source partitions")
    foundation = Path(foundation).resolve() if foundation else None
    foundation_identity = None
    if foundation:
        metadata = json.loads((foundation / "run.json").read_text())
        if (metadata.get("status") != "complete" or metadata.get("rows") != expected
                or metadata.get("configuration", {}).get("snapshot_date") != source["openalex_snapshot_date"]
                or metadata.get("configuration", {}).get("corpus") != "all-works-core-and-xpac"):
            raise ValueError("Foundation is not complete or has different coverage")
        foundation_identity = {"path": str(foundation), "run_sha256": windows.digest_file(foundation / "run.json")}
    config = {"version": VERSION, "source_sha256": windows.digest_file(manifest_path),
              "window_code_sha256": windows.digest_file(windows.__file__),
              "bulk_code_sha256": windows.digest_file(__file__), "compression_level": compression_level,
              "foundation": foundation_identity}
    config_sha256 = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config_path = destination / "config.json"
        if config_path.exists() and json.loads(config_path.read_text()) != config:
            raise ValueError("Immutable dataset configuration mismatch")
        atomic_json(config_path, config)
        (destination / "partitions").mkdir(exist_ok=True)
        tasks = [{"manifest": str(manifest_path), "destination": str(destination / "partitions" / f"part-{index:06d}"),
                  "index": index, "expected_rows": partition["rows"], "source_file": partition["file"],
                  "source_partition_sha256": partition["sha256"], "source_sha256": config["source_sha256"],
                  "window_code_sha256": config["window_code_sha256"], "compression_level": compression_level,
                  "minimum_free_bytes": minimum_free_bytes} for index, partition in enumerate(source["partitions"])]
        completed = []
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn")) as pool:
            for result in pool.map(export_partition, tasks, chunksize=1):
                completed.append(result)
                atomic_json(destination / "progress.json", {"status": "running", "completed_partitions": len(completed),
                            "expected_partitions": len(tasks), "focal_rows": sum(part["outputs"]["focal"]["rows"] for part in completed)})
        previous = -1
        summaries = {group: Counter() for group in ("computation_status", "is_mature", "flags")}
        for part in completed:
            if part["outputs"]["focal"]["rows"]:
                if part["first_node_index"] != previous + 1:
                    raise ValueError("Missing or overlapping focal partition indices")
                if part["last_node_index"] - part["first_node_index"] + 1 != part["outputs"]["focal"]["rows"]:
                    raise ValueError("Non-contiguous all-graph partition indices")
                previous = part["last_node_index"]
            for group, rows in part.pop("quality").items():
                for row in rows:
                    summaries[group][(row["policy"], row["window"], row["value"])] += row["rows"]
        if previous + 1 != expected:
            raise ValueError("Incomplete all-graph index coverage")
        quality = {group: [{"policy": key[0], "window": key[1], "value": key[2], "rows": count}
                           for key, count in counts.items()] for group, counts in summaries.items()}
        atomic_json(destination / "quality.json", quality)
        write_views(destination, foundation)
        result = {"complete": True, "schema_version": "disruption-v1", "calculation_version": VERSION,
                  "config_sha256": config_sha256, "config": config, "source_manifest": str(manifest_path),
                  "source_provenance": {key: value for key, value in source.items() if key != "partitions"},
                  "scope": "all_graph_works", "focal_rows": expected, "window_rows": expected * 8,
                  "annual_rows": sum(part["outputs"]["annual"]["rows"] for part in completed),
                  "partitions": completed, "validation": {"all_source_checksums": True,
                      "contiguous_full_graph_indices": True, "eight_unique_window_groups_per_focal": True,
                      "nonnegative_counts": True, "score_bounds_and_eligibility": True,
                      "count_consistency_policy": "warning_only"},
                  "quality_sha256": windows.digest_file(destination / "quality.json"),
                  "views_sha256": windows.digest_file(destination / "views.sql")}
        atomic_json(destination / "manifest.json", result)
        atomic_json(destination / "progress.json", {"status": "complete", "completed_partitions": len(tasks), "focal_rows": expected})
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--foundation", type=Path)
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--compression-level", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(materialize_all(args.manifest, args.destination, args.workers,
                                   args.compression_level, args.foundation)))


if __name__ == "__main__":
    main()
