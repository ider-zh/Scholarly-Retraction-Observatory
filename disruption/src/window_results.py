"""Stream completed annual graph statistics into compressed, versioned analytical tables."""

import argparse
from datetime import date, datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq


VERSION = "windows-v1"
POLICIES = ("exclude_publication_year", "include_publication_year")
COUNTS = ("NF", "NB", "NR", "citation_count", "future_related_count")
CHECK_FIELDS = (("citation_partition_delta", pa.int64()),
                ("citation_count_consistent", pa.bool_()),
                ("neighborhood_partition_delta", pa.int64()),
                ("neighborhood_count_consistent", pa.bool_()))
ANNUAL_SCHEMA = pa.schema([
    ("work_id", pa.string()), ("age_year", pa.int32()),
    *[(name, pa.int64()) for name in COUNTS], *CHECK_FIELDS,
    ("is_partial_calendar_year", pa.bool_()),
])
FOCAL_SCHEMA = pa.schema([
    ("work_id", pa.string()), ("work_id_numeric", pa.uint64()),
    ("graph_node_index", pa.uint64()), ("publication_year", pa.int32()),
    *[(name, pa.int64()) for name in (
        "reference_count_raw", "reference_count_resolved_unique", "reference_count_valid",
        "graph_indegree_all", "openalex_cited_by_count", "openalex_graph_citation_count_delta",
        "incoming_same_year_count", "incoming_earlier_year_count", "incoming_unknown_year_count",
        "incoming_after_snapshot_year_count")],
    ("has_references", pa.bool_()), ("reference_list_unknown", pa.bool_()),
    ("computation_status", pa.string()), ("observed_age_start", pa.int32()),
    ("observed_age_end", pa.int32()), ("sparse_zero_coverage_complete", pa.bool_()),
    ("source_record_json", pa.string()),
])
WINDOW_SCHEMA = pa.schema([
    ("work_id", pa.string()), ("window_policy", pa.string()), ("window", pa.string()),
    *[(name, pa.string()) for name in (
        "planned_start_date", "planned_end_date", "observed_end_date")],
    ("observed_age_start", pa.int32()), ("observed_age_end", pa.int32()),
    ("is_mature", pa.bool_()), ("snapshot_limited", pa.bool_()),
    ("computation_status", pa.string()),
    *[(name, pa.int64()) for name in COUNTS], *CHECK_FIELDS,
    *[(name, pa.float64()) for name in (
        "disruption_cd_raw_observed", "disruption_no_nr_raw_observed",
        "disruption_cd", "disruption_no_nr")],
    ("flags", pa.list_(pa.string())),
])


def digest_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def consistency(counts):
    citation = counts["citation_count"] - counts["NF"] - counts["NB"]
    neighborhood = counts["future_related_count"] - sum(counts[name] for name in ("NF", "NB", "NR"))
    return {"citation_partition_delta": citation, "citation_count_consistent": citation == 0,
            "neighborhood_partition_delta": neighborhood,
            "neighborhood_count_consistent": neighborhood == 0}


def valid_year(year):
    return type(year) is int and 1 <= year <= 9999


def validate_record(record, snapshot_date):
    if not re.fullmatch(r"https://openalex.org/W[1-9][0-9]*", record.get("work_id", "")):
        raise ValueError("Invalid Work URL ID")
    if type(record.get("graph_node_index")) is not int or not 0 <= record["graph_node_index"] < 2**64:
        raise ValueError("Missing or invalid graph node index")
    status = record.get("computation_status")
    if status not in ("complete", "unavailable_publication_year", "outside_observation_range"):
        raise ValueError("Annual record is not a completed calculation")
    known = valid_year(record.get("publication_year"))
    if (status != "unavailable_publication_year") != known:
        raise ValueError("Annual completion status conflicts with focal year")
    if known and (status == "outside_observation_range") != (record["publication_year"] > snapshot_date.year):
        raise ValueError("Annual completion status conflicts with observation range")
    for name in ("reference_count_raw", "reference_count_resolved_unique", "reference_count_valid",
                 "graph_indegree_all", "openalex_cited_by_count"):
        value = record.get(name)
        if value is not None and (type(value) is not int or not 0 <= value < 2**63):
            raise ValueError(f"Invalid integer count: {name}")
    reference_count = record.get("reference_count_valid")
    if known and reference_count is None:
        raise ValueError("Completed focal lacks valid reference count")
    if not known and reference_count is not None:
        raise ValueError("Unknown focal year has a defined reference count")
    if record.get("has_references") is not (reference_count > 0 if reference_count is not None else None):
        raise ValueError("has_references conflicts with reference count")
    if type(record.get("reference_list_unknown")) is not bool:
        raise ValueError("Missing reference-list completeness flag")
    rows = record.get("annual_counts")
    if not isinstance(rows, list) or (not known and rows):
        raise ValueError("Invalid annual statistics")
    if status == "complete" and (record.get("observed_age_start") != 0 or
            record.get("observed_age_end") != snapshot_date.year - record["publication_year"]):
        raise ValueError("Missing or incomplete observable annual coverage")
    if status != "complete" and rows:
        raise ValueError("Unavailable focal has annual statistics")
    previous_age = -1
    for row in rows:
        age = row.get("age_year")
        if type(age) is not int or age <= previous_age or age > snapshot_date.year - record["publication_year"]:
            raise ValueError("Annual ages must be unique, ordered and observable")
        previous_age = age
        for name in COUNTS:
            if type(row.get(name)) is not int or not 0 <= row[name] < 2**63:
                raise ValueError(f"Invalid annual count: {name}")
        partial = date(record["publication_year"] + age, 12, 31) > snapshot_date
        if row.get("is_partial_calendar_year") is not partial:
            raise ValueError("Partial calendar-year flag conflicts with snapshot date")


def window_result(record, policy, years, snapshot_date):
    if policy not in POLICIES or (years != "lifetime" and (type(years) is not int or years < 1)):
        raise ValueError("Invalid window definition")
    if isinstance(snapshot_date, str):
        snapshot_date = date.fromisoformat(snapshot_date)
    lifetime = years == "lifetime"
    focal_year = record.get("publication_year")
    known = valid_year(focal_year)
    start_age = int(policy == POLICIES[0])
    start_year = focal_year + start_age if known else None
    end_year = focal_year + start_age + years - 1 if known and not lifetime else None
    start = date(start_year, 1, 1) if start_year is not None and start_year <= 9999 else None
    end = date(end_year, 12, 31) if end_year is not None and end_year <= 9999 else None
    observable = start is not None and start <= snapshot_date
    complete = record.get("computation_status") == "complete"
    available = observable and complete
    observed_end = min(end or snapshot_date, snapshot_date) if observable else None
    mature = end <= snapshot_date if end is not None else None
    selected = [row for row in record.get("annual_counts", [])
                if start_age <= row["age_year"] <= snapshot_date.year - focal_year
                and (lifetime or row["age_year"] < start_age + years)] if known else []
    counts = {name: sum(row[name] for row in selected) if available else None for name in COUNTS}
    checks = {name: None for name, _ in CHECK_FIELDS}
    flags = []
    if known and (start is None or (not lifetime and end is None)):
        flags.append("unrepresentable_window_bounds")
    if record.get("reference_count_valid") == 0:
        flags.append("no_references")
    if not known or not complete or record.get("reference_list_unknown"):
        flags.append("incomplete_record")
    if mature is False:
        flags.append("insufficient_observation_window")
    if lifetime:
        flags.append("snapshot_limited")
    source_count = record.get("openalex_cited_by_count")
    if source_count is not None and source_count != record.get("graph_indegree_all"):
        flags.append("openalex_graph_citation_count_warning")
    raw_cd = raw_no_nr = None
    if available:
        checks = consistency(counts)
        direct = counts["NF"] + counts["NB"]
        denominator = direct + counts["NR"]
        numerator = counts["NF"] - counts["NB"]
        raw_cd = numerator / denominator if denominator else None
        raw_no_nr = numerator / direct if direct else None
        for condition, flag in (
            (counts["citation_count"] == 0, "no_future_citations"),
            (not denominator, "empty_denominator_cd"), (not direct, "empty_denominator_no_nr"),
            (not checks["citation_count_consistent"], "citation_partition_warning"),
            (not checks["neighborhood_count_consistent"], "neighborhood_partition_warning"),
        ):
            if condition:
                flags.append(flag)
    interpreted = (available and record.get("has_references") is True
                   and not record.get("reference_list_unknown") and (lifetime or mature is True))
    return {
        "work_id": record["work_id"], "window_policy": policy,
        "window": "lifetime" if lifetime else f"{years}y",
        "planned_start_date": start.isoformat() if start else None,
        "planned_end_date": end.isoformat() if end else None,
        "observed_end_date": observed_end.isoformat() if observed_end else None,
        "observed_age_start": start_age if observable else None,
        "observed_age_end": observed_end.year - focal_year if observed_end else None,
        "is_mature": mature, "snapshot_limited": lifetime,
        "computation_status": record.get("computation_status") if observable else "unobservable",
        **counts, **checks, "disruption_cd_raw_observed": raw_cd,
        "disruption_no_nr_raw_observed": raw_no_nr,
        "disruption_cd": raw_cd if interpreted else None,
        "disruption_no_nr": raw_no_nr if interpreted else None, "flags": flags,
    }


class BufferedTable:
    def __init__(self, path, schema, batch_rows, compression_level):
        self.writer = pq.ParquetWriter(path, schema, compression="zstd", compression_level=compression_level)
        self.schema = schema
        self.batch_rows = batch_rows
        self.rows = []
        self.count = 0

    def append(self, row):
        self.rows.append(row)
        self.count += 1
        if len(self.rows) >= self.batch_rows:
            self.flush()

    def flush(self):
        if self.rows:
            self.writer.write_table(pa.Table.from_pylist(self.rows, schema=self.schema))
            self.rows.clear()

    def close(self):
        self.flush()
        self.writer.close()


def materialize(manifest_path, destination, batch_rows=4096, compression_level=1, partition_index=0):
    if not 1 <= batch_rows <= 4096:
        raise ValueError("batch_rows must be between 1 and 4096")
    if type(partition_index) is not int or partition_index < 0:
        raise ValueError("partition_index must be nonnegative")
    manifest_path, destination = Path(manifest_path), Path(destination)
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("complete") is not True or manifest.get("schema_version") != "disruption-annual-v1":
        raise ValueError("Annual partition manifest is not complete")
    if manifest.get("sparse_zero_semantics") != "complete_observable_bins":
        raise ValueError("Missing explicit sparse annual coverage guarantee")
    snapshot_date = date.fromisoformat(manifest["openalex_snapshot_date"])
    annual = manifest["partitions"][partition_index]
    source = manifest_path.parent / annual["file"]
    if digest_file(source) != annual["sha256"]:
        raise ValueError("Annual partition checksum mismatch")
    config = {"version": VERSION, "input_manifest_sha256": digest_file(manifest_path),
              "partition_index": partition_index,
              "policies": POLICIES, "windows": [3, 5, 10, "lifetime"],
              "compression": "zstd", "compression_level": compression_level,
              "code_sha256": digest_file(__file__)}
    config_sha256 = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    if destination.exists():
        raise FileExistsError("Immutable output already exists; use a new partition directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    tables = {}
    try:
        for name, schema in (("focal", FOCAL_SCHEMA), ("annual", ANNUAL_SCHEMA), ("windows", WINDOW_SCHEMA)):
            tables[name] = BufferedTable(temporary / f"{name}.parquet", schema, batch_rows, compression_level)
        previous_node_index = -1
        warning_rows = 0
        with gzip.open(source, "rt", encoding="utf-8") as stream:
            for line in stream:
                record = json.loads(line)
                validate_record(record, snapshot_date)
                identifier = int(record["work_id"].rsplit("W", 1)[1])
                node_index = record["graph_node_index"]
                if node_index <= previous_node_index:
                    raise ValueError("Focal graph node indices must be unique and ordered")
                previous_node_index = node_index
                complete = record["computation_status"] == "complete"
                age_end = snapshot_date.year - record["publication_year"] if complete else None
                focal = {key: value for key, value in record.items() if key != "annual_counts"}
                tables["focal"].append({**focal,
                    "work_id_numeric": identifier,
                    "observed_age_start": 0 if complete and age_end >= 0 else None,
                    "observed_age_end": age_end if complete and age_end >= 0 else None,
                    "sparse_zero_coverage_complete": complete,
                    "source_record_json": json.dumps(focal, sort_keys=True, ensure_ascii=False)})
                for row in record["annual_counts"]:
                    tables["annual"].append({"work_id": record["work_id"], **row, **consistency(row)})
                for policy in POLICIES:
                    for years in (3, 5, 10, "lifetime"):
                        row = window_result(record, policy, years, snapshot_date)
                        warning_rows += any(flag.endswith("warning") for flag in row["flags"])
                        tables["windows"].append(row)
        if tables["focal"].count != annual["rows"]:
            raise ValueError("Annual partition row count mismatch")
        for table in tables.values():
            table.close()
        outputs = {}
        for name, table in tables.items():
            path = temporary / f"{name}.parquet"
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
            outputs[name] = {"path": path.name, "rows": table.count,
                             "bytes": path.stat().st_size, "sha256": digest_file(path)}
        source_provenance = {key: value for key, value in manifest.items() if key != "partitions"}
        source_provenance.update({"manifest_path": str(manifest_path.resolve()),
                                  "manifest_sha256": config["input_manifest_sha256"],
                                  "partition": annual})
        result = {"status": "complete", "schema_version": "disruption-v1",
                  "calculation_version": VERSION, "config_sha256": config_sha256, "config": config,
                  "snapshot_date": snapshot_date.isoformat(), "source_provenance": source_provenance,
                  "generated_at": datetime.now(timezone.utc).isoformat(), "outputs": outputs,
                  "window_rows_with_warnings": warning_rows,
                  "count_semantics": "observed_counts",
                  "sparse_zero_semantics": manifest["sparse_zero_semantics"]}
        with (temporary / "manifest.json").open("w") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        descriptor = os.open(temporary, os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.rename(temporary, destination)
        descriptor = os.open(destination.parent, os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return result
    except BaseException:
        for table in tables.values():
            try:
                table.writer.close()
            except Exception:
                pass
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--batch-rows", type=int, default=4096)
    parser.add_argument("--compression-level", type=int, default=1)
    parser.add_argument("--partition-index", type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(materialize(args.manifest, args.destination, args.batch_rows,
                                 args.compression_level, args.partition_index)))


if __name__ == "__main__":
    main()
