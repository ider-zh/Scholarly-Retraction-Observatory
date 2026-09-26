"""Independent, immutable annual-bin quality audit of a completed all-graph export."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import tempfile

import duckdb
import pyarrow.parquet as pq

from disruption.src.bulk_results import atomic_json, sql_literal
from disruption.src.window_results import ANNUAL_SCHEMA, COUNTS, digest_file


VERSION = "annual-quality-v1"


def contained_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Artifact path escapes published dataset")
    return path


def audit_partition(task):
    root, part = Path(task["root"]), task["partition"]
    directory = contained_path(root / "partitions", part["path"])
    manifest_path = directory / "manifest.json"
    if digest_file(manifest_path) != part["manifest_sha256"]:
        raise ValueError("Partition manifest checksum mismatch")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("status") != "complete" or manifest["outputs"] != part["outputs"]:
        raise ValueError("Partition is incomplete or output metadata differs")
    metadata = part["outputs"]["annual"]
    path = contained_path(directory, metadata["path"])
    if digest_file(path) != metadata["sha256"]:
        raise ValueError("Annual checksum mismatch")
    parquet = pq.ParquetFile(path)
    if parquet.metadata.num_rows != metadata["rows"]:
        raise ValueError("Annual row coverage mismatch")
    if not parquet.schema_arrow.equals(ANNUAL_SCHEMA, check_metadata=False):
        raise ValueError("Annual schema mismatch")
    connection = duckdb.connect(config={"threads": "1", "memory_limit": "1GiB"})
    try:
        connection.execute("SET temp_directory = ''")
        connection.execute(f"CREATE VIEW annual AS SELECT *, CAST(citation_count AS HUGEINT)-NF-NB AS citation_actual, CAST(future_related_count AS HUGEINT)-NF-NB-NR AS neighborhood_actual FROM read_parquet({sql_literal(path)})")
        negative = " OR ".join(f"{name} < 0" for name in COUNTS)
        missing = " OR ".join(f"{name} IS NULL" for name in (*COUNTS, "work_id", "age_year"))
        rows, negatives, invalid = connection.execute(f"SELECT count(*), count(*) FILTER (WHERE {negative}), count(*) FILTER (WHERE {missing} OR age_year < 0) FROM annual").fetchone()
        if rows != metadata["rows"] or negatives or invalid:
            raise ValueError(f"Annual structural failures: rows={rows}, negative={negatives}, invalid={invalid}")
        result = {"index": part["index"], "annual_rows": rows, "negative_count_rows": negatives}
        for prefix, flag in (("citation", "citation_count_consistent"), ("neighborhood", "neighborhood_count_consistent")):
            mismatch, minimum, maximum, total, wrong_delta, wrong_flag = connection.execute(f"""SELECT
                count(*) FILTER (WHERE {prefix}_actual <> 0), min({prefix}_actual), max({prefix}_actual), sum({prefix}_actual),
                count(*) FILTER (WHERE {prefix}_partition_delta IS DISTINCT FROM {prefix}_actual),
                count(*) FILTER (WHERE {flag} IS DISTINCT FROM ({prefix}_actual = 0)) FROM annual""").fetchone()
            result[prefix] = {"mismatched_rows": mismatch, "minimum_delta": minimum, "maximum_delta": maximum,
                              "sum_delta": total or 0, "misreported_delta_rows": wrong_delta, "misreported_flag_rows": wrong_flag}
        return result
    finally:
        connection.close()


def audit_all(manifest_path, destination, workers=32):
    if not 1 <= workers <= 32:
        raise ValueError("Workers must be between 1 and 32")
    manifest_path, destination = Path(manifest_path).resolve(), Path(destination).resolve()
    if destination.exists() or destination.is_relative_to(manifest_path.parent):
        raise ValueError("Audit destination must be new and outside the published dataset")
    source_hash = digest_file(manifest_path)
    source = json.loads(manifest_path.read_text())
    if source.get("complete") is not True or source.get("scope") != "all_graph_works":
        raise ValueError("Complete all-graph analytical manifest required")
    expected = source["source_provenance"]["graph_work_count"]
    if (source["source_provenance"].get("complete") is not True
            or source["source_provenance"].get("scope") != "all_graph_works"
            or source["source_provenance"]["requested_focal_count"] != expected
            or source["focal_rows"] != expected or source["window_rows"] != expected * 8):
        raise ValueError("Full-graph coverage mismatch")
    parts = source["partitions"]
    if len({part["path"] for part in parts}) != len(parts) or [part["index"] for part in parts] != list(range(len(parts))):
        raise ValueError("Duplicate or unordered partitions")
    previous = -1
    for part in parts:
        rows = part["outputs"]["focal"]["rows"]
        if part["outputs"]["windows"]["rows"] != rows * 8:
            raise ValueError("Partition window coverage mismatch")
        if rows:
            if part["first_node_index"] != previous + 1 or part["last_node_index"] != previous + rows:
                raise ValueError("Noncontiguous focal coverage")
            previous = part["last_node_index"]
    if previous + 1 != expected or sum(part["outputs"]["annual"]["rows"] for part in parts) != source["annual_rows"]:
        raise ValueError("Aggregate coverage mismatch")
    tasks = [{"root": str(manifest_path.parent), "partition": part} for part in parts]
    if workers == 1:
        results = [audit_partition(task) for task in tasks]
    else:
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn")) as pool:
            results = list(pool.map(audit_partition, tasks, chunksize=1))
    quality = {"annual_rows": sum(result["annual_rows"] for result in results), "negative_count_rows": 0,
               "count_consistency_policy": "warning_only", "partitions": results}
    for prefix in ("citation", "neighborhood"):
        summaries = [result[prefix] for result in results]
        quality[prefix] = {key: sum(summary[key] for summary in summaries) for key in
                           ("mismatched_rows", "sum_delta", "misreported_delta_rows", "misreported_flag_rows")}
        for key, operation in (("minimum_delta", min), ("maximum_delta", max)):
            values = [summary[key] for summary in summaries if summary[key] is not None]
            quality[prefix][key] = operation(values) if values else None
    if digest_file(manifest_path) != source_hash:
        raise ValueError("Published manifest changed during audit")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".annual-quality-", dir=destination.parent))
    try:
        atomic_json(staging / "quality.json", quality)
        result = {"complete": True, "version": VERSION, "generated_at": datetime.now(timezone.utc).isoformat(),
                  "source_manifest": str(manifest_path), "source_manifest_sha256": source_hash,
                  "code_sha256": digest_file(__file__), "duckdb_version": duckdb.__version__,
                  "workers": workers, "threads_per_worker": 1, "partitions": len(results),
                  "annual_rows": quality["annual_rows"], "focal_rows": expected,
                  "quality_sha256": digest_file(staging / "quality.json"), "count_consistency_policy": "warning_only"}
        atomic_json(staging / "manifest.json", result)
        os.rename(staging, destination)
        descriptor = os.open(destination.parent, os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return result
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--workers", type=int, default=32)
    args = parser.parse_args()
    print(json.dumps(audit_all(args.manifest, args.destination, args.workers)))


if __name__ == "__main__":
    main()
