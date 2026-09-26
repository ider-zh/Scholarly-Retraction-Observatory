"""Versioned, resumable snapshot projection; does not compute network statistics."""

import argparse
import concurrent.futures
import datetime
import fcntl
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import struct
import time

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq


VERSION = "foundation-v1"
COLUMNS = ["id", "doi", "publication_year", "publication_date", "type",
           "is_retracted", "is_xpac", "language", "primary_topic",
           "primary_location", "cited_by_count", "referenced_works"]


def digest_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def source_identity(path):
    stat = path.stat()
    with path.open("rb") as stream:
        stream.seek(-8, 2)
        trailer = stream.read(8)
        if trailer[4:] != b"PAR1":
            raise ValueError(f"Invalid Parquet trailer: {path}")
        footer_length = struct.unpack("<I", trailer[:4])[0]
        stream.seek(-8 - footer_length, 2)
        footer = stream.read(footer_length)
    return {"bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns,
            "footer_sha256": hashlib.sha256(footer).hexdigest(),
            "fingerprint_scope": "stat-and-parquet-footer-not-full-file"}


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".partial")
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


def disk_guard(root, initial_free, minimum_free, maximum_extra):
    free = shutil.disk_usage(root).free
    if free < minimum_free or initial_free - free > maximum_extra:
        raise RuntimeError("Disk safety threshold reached; committed shards remain resumable")


def projection_sql(snapshot_date):
    return f"""
        SELECT id AS work_id,
          CASE WHEN regexp_full_match(id, 'https://openalex[.]org/W[1-9][0-9]*')
            THEN try_cast(substr(id, 23) AS UBIGINT) END AS work_id_numeric,
          doi, publication_year, publication_date,
          'unknown'::VARCHAR AS publication_date_precision,
          type AS work_type, is_retracted, is_xpac, language,
          primary_location.source.id AS source_id,
          primary_location.source.type AS source_type,
          primary_topic.id AS primary_topic_id,
          primary_topic.display_name AS primary_topic_name,
          primary_topic.id IS NOT NULL AS has_primary_topic,
          primary_topic.subfield.id AS subfield_id,
          primary_topic.subfield.display_name AS subfield_name,
          primary_topic.field.id AS field_id,
          primary_topic.field.display_name AS field_name,
          primary_topic.domain.id AS domain_id,
          primary_topic.domain.display_name AS domain_name,
          cited_by_count::BIGINT AS openalex_cited_by_count,
          coalesce(publication_year BETWEEN 1 AND 9999, false) AS has_valid_publication_year,
          list_filter([
            CASE WHEN publication_year IS NULL THEN 'missing_year'
              WHEN publication_year NOT BETWEEN 1 AND 9999 THEN 'invalid_year' END,
            CASE WHEN publication_date IS NULL THEN 'missing_date' END,
            CASE WHEN year(publication_date) != publication_year THEN 'date_year_conflict' END,
            CASE WHEN publication_date > DATE '{snapshot_date}' THEN 'future_date' END,
            CASE WHEN publication_year > year(DATE '{snapshot_date}') THEN 'future_year' END
          ], flag -> flag IS NOT NULL) AS date_quality_flags,
          len(referenced_works)::BIGINT AS reference_count_raw
        FROM batch
    """


def build_shard(task):
    path = Path(task["path"])
    destination = Path(task["destination"])
    destination.mkdir(parents=True, exist_ok=True)
    checkpoint = destination / "complete.json"
    initial_identity = source_identity(path)
    if initial_identity != task["identity"]:
        raise RuntimeError(f"Source changed before projection: {path}")
    if checkpoint.exists():
        saved = json.loads(checkpoint.read_text())
        if saved["input"] != initial_identity or saved["config_sha256"] != task["config_sha256"]:
            raise RuntimeError(f"Checkpoint identity mismatch: {checkpoint}")
        for name, metadata in saved["outputs"].items():
            output = destination / name
            if not output.exists() or digest_file(output) != metadata["sha256"]:
                raise RuntimeError(f"Output checksum failure: {output}")
        return {**saved, "resumed": True}
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    connection = duckdb.connect(config={"threads": "1", "memory_limit": f"{task['worker_memory_gib']}GiB"})
    connection.execute("SET preserve_insertion_order = true")
    connection.execute("SET temp_directory = ''")
    source = pq.ParquetFile(path)
    missing = set(COLUMNS) - set(source.schema_arrow.names)
    if missing:
        raise ValueError(f"Missing snapshot columns {sorted(missing)} in {path}")
    if source.metadata.num_rows != task["expected_rows"]:
        raise ValueError(f"Manifest row count mismatch: {path}")
    writers = {}
    rows = 0
    raw_entries = 0
    unknown_lists = 0
    started = time.monotonic()
    try:
        for batch in source.iter_batches(batch_size=task["batch_rows"], columns=COLUMNS, use_threads=False):
            disk_guard(destination, task["initial_free"], task["minimum_free"], task["maximum_extra"])
            connection.register("batch", pa.Table.from_batches([batch]))
            nodes = connection.execute(projection_sql(task["snapshot_date"])).fetch_arrow_table()
            references = pa.Table.from_arrays([batch.column("id"), batch.column("referenced_works")],
                                              names=["work_id", "referenced_works"])
            counts = connection.execute("SELECT sum(len(referenced_works)), count(*) FILTER (WHERE referenced_works IS NULL) FROM batch").fetchone()
            raw_entries += counts[0] or 0
            unknown_lists += counts[1]
            for name, table in (("nodes", nodes), ("raw_references", references)):
                if name not in writers:
                    writers[name] = pq.ParquetWriter(destination / f"{name}.parquet.partial", table.schema,
                                                     compression="zstd", compression_level=task["compression_level"])
                writers[name].write_table(table, row_group_size=task["batch_rows"])
            rows += batch.num_rows
        if rows != source.metadata.num_rows:
            raise RuntimeError(f"Projection lost rows: {path}")
        if not writers:
            empty = pa.RecordBatch.from_arrays([pa.array([], type=source.schema_arrow.field(name).type) for name in COLUMNS], names=COLUMNS)
            connection.register("batch", empty)
            tables = {"nodes": connection.execute(projection_sql(task["snapshot_date"])).fetch_arrow_table(),
                      "raw_references": pa.Table.from_arrays([empty.column("id"), empty.column("referenced_works")], names=["work_id", "referenced_works"])}
            for name, table in tables.items():
                writers[name] = pq.ParquetWriter(destination / f"{name}.parquet.partial", table.schema, compression="zstd", compression_level=task["compression_level"])
        for writer in writers.values():
            writer.close()
        if source_identity(path) != initial_identity:
            raise RuntimeError(f"Source changed during projection: {path}")
        outputs = {}
        for name in writers:
            temporary = destination / f"{name}.parquet.partial"
            with temporary.open("rb") as stream:
                os.fsync(stream.fileno())
            output = destination / f"{name}.parquet"
            os.replace(temporary, output)
            if pq.ParquetFile(output).metadata.num_rows != rows:
                raise RuntimeError(f"Output row count mismatch: {output}")
            outputs[output.name] = {"sha256": digest_file(output), "bytes": output.stat().st_size}
        result = {"status": "complete", "source": task["relative_path"], "input": initial_identity,
                  "config_sha256": task["config_sha256"], "rows": rows,
                  "raw_reference_entries": raw_entries, "unknown_reference_lists": unknown_lists,
                  "outputs": outputs, "wall_seconds": time.monotonic() - started,
                  "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  "graph_validation": "not_computed"}
        atomic_json(checkpoint, result)
        return result
    finally:
        for writer in writers.values():
            writer.close()
        connection.close()


def process_rss_bytes(process_id):
    try:
        values = Path(f"/proc/{process_id}/statm").read_text().split()
        return int(values[1]) * os.sysconf("SC_PAGE_SIZE")
    except FileNotFoundError:
        return 0


def run(args):
    if not 1 <= args.workers <= 40 or not 1 <= args.memory_gib <= 384:
        raise ValueError("Resources must be within 1..40 workers and 1..384 GiB")
    if args.batch_rows < 1 or args.batch_rows > 262144:
        raise ValueError("batch-rows must be within 1..262144")
    if args.max_files is not None and args.max_files < 1:
        raise ValueError("max-files must be positive")
    if not 0 <= args.min_free_tb or not 0 < args.max_extra_tb <= 4:
        raise ValueError("Invalid disk budget")
    if args.min_free_tb < 1 and not args.allow_small_test_disk:
        raise ValueError("Production must reserve at least 1 decimal TB")
    root = Path(args.source).resolve()
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    snapshot_date = datetime.date.fromisoformat(manifest["date"]).isoformat()
    entries = next(entity for entity in manifest["entities"] if entity["entity"] == "works")["files"]
    entries = sorted(entries, key=lambda entry: entry["meta"]["content_length"], reverse=True)
    validation = None
    validated_files = {}
    if not args.allow_small_test_disk:
        pointer_path = Path(args.validated_source)
        pointer = json.loads(pointer_path.read_text())
        report_path = Path(pointer["report"])
        report = json.loads(report_path.read_text())
        inventory_path = report_path.parent / "files.json"
        validated_files = {entry["key"]: entry for entry in json.loads(inventory_path.read_text()) if entry["entity"] == "works"}
        if (pointer["manifest_sha256"] != digest_file(manifest_path)
                or report["manifest_sha256"] != pointer["manifest_sha256"]
                or report["status"] != "validated"
                or report["source_acceptance_policy"] != "retrospective-v1"):
            raise ValueError("Accepted validation report does not match this snapshot")
        validation = {"pointer": str(pointer_path), "pointer_sha256": digest_file(pointer_path),
                      "report": str(report_path), "report_sha256": digest_file(report_path),
                      "files": str(inventory_path), "files_sha256": digest_file(inventory_path),
                      "transfer_provenance": report["transfer_provenance"],
                      "source_acceptance_policy": report["source_acceptance_policy"],
                      "deletion_log": report.get("deletion_log")}
    code_sha256 = digest_file(Path(__file__))
    config = {"schema_version": VERSION, "calculation_version": VERSION,
              "code_sha256": code_sha256, "snapshot_manifest_sha256": digest_file(manifest_path),
              "snapshot_date": snapshot_date, "compression": "zstd",
              "compression_level": args.compression_level, "batch_rows": args.batch_rows,
              "corpus": "all-works-core-and-xpac", "reference_policy": "raw-unchanged",
              "date_precision": "unknown", "duckdb_version": duckdb.__version__, "pyarrow_version": pa.__version__,
              "accepted_validation": validation,
              "input_fingerprint_scope": "stat-and-parquet-footer-not-full-file"}
    config_sha256 = digest_json(config)
    output = Path(args.output).resolve()
    if not args.allow_small_test_disk and not output.is_relative_to(Path("/mnt/hg02")):
        raise ValueError("Production output must reside under /mnt/hg02")
    run_root = output / config["snapshot_manifest_sha256"] / config_sha256
    run_root.mkdir(parents=True, exist_ok=True)
    lock = (run_root / ".lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    metadata_path = run_root / "run.json"
    initial_free = shutil.disk_usage(run_root).free
    if metadata_path.exists():
        previous = json.loads(metadata_path.read_text())
        initial_free = previous["initial_free_bytes"]
    metadata = {"configuration": config, "config_sha256": config_sha256,
                "source_root": str(root), "initial_free_bytes": initial_free,
                "workers": args.workers, "memory_gib": args.memory_gib,
                "minimum_free_bytes": int(args.min_free_tb * 10**12),
                "maximum_extra_bytes": int(args.max_extra_tb * 10**12),
                "provenance_policy": "retrospective-v1",
                "provenance_gap": "Pre-download manifest capture and transfer log not established by this projection",
                "expected_shards": len(entries), "status": "running", "network_statistics": "not_computed"}
    disk_guard(run_root, initial_free, metadata["minimum_free_bytes"], metadata["maximum_extra_bytes"])
    inventory = {}
    for entry in entries:
        relative = entry["url"].split("/data/parquet/", 1)[1]
        path = root / relative
        if not path.resolve().is_relative_to(root):
            raise ValueError("Manifest path escapes source root")
        identity = source_identity(path)
        if identity["bytes"] != entry["meta"]["content_length"]:
            raise ValueError(f"Manifest byte length mismatch: {path}")
        if validated_files:
            accepted = validated_files.get(relative)
            if (accepted is None or accepted["errors"] or accepted["actual_bytes"] != identity["bytes"]
                    or accepted["mtime_ns"] != identity["mtime_ns"]
                    or accepted["actual_rows"] != entry["meta"]["record_count"]):
                raise ValueError(f"Source no longer matches accepted validation: {path}")
        inventory[relative] = identity
    inventory_path = run_root / "input_inventory.json"
    if inventory_path.exists() and json.loads(inventory_path.read_text()) != inventory:
        raise RuntimeError("Frozen source inventory mismatch; cannot resume changed inputs")
    if not inventory_path.exists():
        atomic_json(inventory_path, inventory)
    metadata["input_inventory_sha256"] = digest_file(inventory_path)
    atomic_json(metadata_path, metadata)
    selected = entries[:args.max_files] if args.max_files else entries
    tasks = []
    for entry in selected:
        relative = entry["url"].split("/data/parquet/", 1)[1]
        path = root / relative
        if not path.resolve().is_relative_to(root):
            raise ValueError("Manifest path escapes source root")
        identity = inventory[relative]
        if identity["bytes"] != entry["meta"]["content_length"]:
            raise ValueError(f"Manifest byte length mismatch: {path}")
        tasks.append({"path": str(path), "relative_path": relative,
                      "destination": str(run_root / "shards" / hashlib.sha256(relative.encode()).hexdigest()[:24]),
                      "identity": identity, "expected_rows": entry["meta"]["record_count"],
                      "config_sha256": config_sha256, "snapshot_date": snapshot_date,
                      "batch_rows": args.batch_rows, "compression_level": args.compression_level,
                      "worker_memory_gib": max(1, args.memory_gib // args.workers // 2),
                      "initial_free": initial_free, "minimum_free": metadata["minimum_free_bytes"],
                      "maximum_extra": metadata["maximum_extra_bytes"]})
    completed = []
    executor = concurrent.futures.ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context("spawn"))
    peak_rss = 0
    try:
        pending = {executor.submit(build_shard, task) for task in tasks}
        while pending:
            done, pending = concurrent.futures.wait(pending, timeout=1, return_when=concurrent.futures.FIRST_COMPLETED)
            rss = process_rss_bytes(os.getpid()) + sum(process_rss_bytes(process.pid) for process in executor._processes.values())
            peak_rss = max(peak_rss, rss)
            if rss > args.memory_gib * 1024**3:
                raise RuntimeError("Aggregate process RSS budget exceeded; stop and resume with smaller batches/workers")
            disk_guard(run_root, initial_free, metadata["minimum_free_bytes"], metadata["maximum_extra_bytes"])
            for future in done:
                result = future.result()
                completed.append(result)
                print(json.dumps({"completed": len(completed), "selected": len(tasks), "source": result["source"], "rows": result["rows"], "resumed": result.get("resumed", False)}), flush=True)
        metadata.update(status="complete" if len(selected) == len(entries) else "pilot_complete",
                        completed_shards=len(completed), rows=sum(item["rows"] for item in completed),
                        raw_reference_entries=sum(item["raw_reference_entries"] for item in completed),
                        peak_process_rss_bytes=peak_rss)
        atomic_json(metadata_path, metadata)
    except BaseException as error:
        for process in executor._processes.values():
            process.terminate()
        metadata.update(status="interrupted", error=str(error), completed_this_invocation=len(completed), peak_process_rss_bytes=peak_rss)
        atomic_json(metadata_path, metadata)
        raise
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
        lock.close()
    print(json.dumps({"run_root": str(run_root), "status": metadata["status"]}), flush=True)
    return run_root


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--source", default="/mnt/hg02/openalex-snapshot/data/parquet")
    result.add_argument("--output", default="/mnt/hg02/openalex-snapshot/analysis/disruption/foundation")
    result.add_argument("--validated-source", default="/mnt/hg02/openalex-snapshot/analysis/validation/validated-source.json")
    result.add_argument("--workers", type=int, default=16)
    result.add_argument("--memory-gib", type=int, default=384)
    result.add_argument("--batch-rows", type=int, default=65536)
    result.add_argument("--compression-level", type=int, default=1)
    result.add_argument("--max-files", type=int)
    result.add_argument("--min-free-tb", type=float, default=1)
    result.add_argument("--max-extra-tb", type=float, default=4)
    result.add_argument("--allow-small-test-disk", action="store_true", help="Synthetic fixtures only; never for production")
    return result


if __name__ == "__main__":
    run(parser().parse_args())
