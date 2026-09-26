"""Publish immutable, non-filtering research convenience views after complete analytics."""

import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile

from disruption.src.window_results import digest_file


VERSION = "research-views-v1"


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def render_sql(base_sql, snapshot, schema_version, calculation_version):
    snapshot_year = date.fromisoformat(snapshot).year
    complete_year = snapshot_year if snapshot.endswith("12-31") else snapshot_year - 1
    audit = {name: f"try_cast(json_extract(source_record_json, '$.reference_quality_counts.{name}') AS BIGINT)"
             for name in ("invalid", "dangling", "self_loop")}
    reference_flags = ",\n  ".join(f"reference_count_valid >= {threshold} AS has_ref_{threshold}" for threshold in (1, 5, 10, 20))
    citation_flags = ",\n  ".join(
        f"CASE WHEN window_observation_eligible THEN citation_count >= {threshold} END AS has_citation_{threshold}"
        for threshold in (5, 10, 20))
    eligibility_flags = ",\n  ".join(
        f"CASE WHEN window_observation_eligible THEN reference_count_valid >= {threshold} AND citation_count >= {threshold} END AS eligible_r{threshold}_c{threshold}"
        for threshold in (5, 10, 20))
    return base_sql + f"""
CREATE OR REPLACE VIEW disruption_research_ready AS
WITH scoped AS (
  SELECT *,
    computation_status = 'complete' AND citation_count IS NOT NULL
      AND (\"window\" = 'lifetime' OR is_mature = true) AS window_observation_eligible
  FROM disruption_research
)
SELECT *,
  {literal(snapshot)}::DATE AS openalex_snapshot_date,
  {literal(schema_version)} AS schema_version,
  {literal(calculation_version)} AS calculation_version,
  {literal(VERSION)} AS research_view_version,
  CASE WHEN has_valid_publication_year THEN {snapshot_year} - publication_year END AS paper_age_at_snapshot,
  CASE WHEN has_valid_publication_year THEN greatest(0, {complete_year} - publication_year) END AS complete_calendar_years_exclude_publication_year,
  CASE WHEN has_valid_publication_year THEN greatest(0, {complete_year} - publication_year + 1) END AS complete_calendar_years_include_publication_year,
  reference_count_valid AS reference_count,
  {reference_flags},
  {citation_flags},
  {eligibility_flags},
  CASE WHEN has_valid_publication_year IS NOT TRUE OR reference_list_unknown IS NOT FALSE THEN NULL
       WHEN {audit['invalid']} IS NULL OR {audit['dangling']} IS NULL OR {audit['self_loop']} IS NULL THEN NULL
       ELSE {audit['invalid']} = 0 AND {audit['dangling']} = 0 AND {audit['self_loop']} = 0 END AS has_valid_reference_graph,
  CASE WHEN computation_status != 'complete' OR citation_count IS NULL THEN NULL
       ELSE citation_count_consistent AND incoming_earlier_year_count = 0
            AND incoming_unknown_year_count = 0 END AS has_valid_citation_graph
FROM scoped;
""" + render_wide_sql()


def render_wide_sql():
    columns = ["work_id", "max(publication_year) AS publication_year",
               "max(openalex_snapshot_date) AS openalex_snapshot_date",
               "max(schema_version) AS schema_version", "max(calculation_version) AS calculation_version",
               "max(research_view_version) AS research_view_version",
               "max(reference_count) AS reference_count", "max(paper_age_at_snapshot) AS paper_age_at_snapshot"]
    for policy in ("exclude_publication_year", "include_publication_year"):
        columns.append(f"max(complete_calendar_years_{policy}) AS complete_calendar_years_{policy}")
        for window in ("3y", "5y", "10y", "lifetime"):
            for metric in ("NF", "NB", "NR", "citation_count", "future_related_count", "is_mature",
                           "disruption_cd_raw_observed", "disruption_no_nr_raw_observed", "disruption_cd",
                           "disruption_no_nr", "flags", "computation_status"):
                alias = f"{metric}_{window}_{policy}"
                if metric == "citation_count" and window == "lifetime":
                    alias = f"future_citation_count_lifetime_{policy}"
                columns.append(f"max({metric}) FILTER (WHERE window_policy = '{policy}' AND \"window\" = '{window}') AS {alias}")
    return "\nCREATE OR REPLACE VIEW disruption_work_wide AS\nSELECT " + ",\n  ".join(columns) + "\nFROM disruption_research_ready GROUP BY work_id;\n"


def render_custom_windows(snapshot):
    counts = ("NF", "NB", "NR", "citation_count", "future_related_count")
    aggregates = ",\n    ".join(f"CASE WHEN available THEN cast(coalesce(sum(annual.{name}), 0) AS BIGINT) END AS {name}" for name in counts)
    return f"""CREATE OR REPLACE MACRO disruption_age_range(first_age, last_age) AS TABLE (
  WITH coverage AS (
    SELECT *, first_age AS requested_age_start, last_age AS requested_age_end,
      computation_status = 'complete' AND sparse_zero_coverage_complete
        AND first_age >= observed_age_start AND first_age <= observed_age_end
        AND last_age >= first_age AND first_age = floor(first_age) AND last_age = floor(last_age) AS available,
      CASE WHEN publication_year BETWEEN 1 AND 9999
        AND publication_year + last_age BETWEEN 1 AND 9999 AND first_age >= 0 AND last_age >= first_age
        THEN make_date(publication_year + last_age, 12, 31) <= DATE {literal(snapshot)} END AS is_mature
    FROM disruption_focal
  ), aggregated AS (
    SELECT focal.work_id, focal.publication_year, focal.reference_count_valid, focal.reference_list_unknown,
      focal.computation_status, focal.requested_age_start, focal.requested_age_end,
      focal.available, focal.is_mature,
      CASE WHEN focal.available THEN least(last_age, focal.observed_age_end) END AS observed_age_end,
      {aggregates}
    FROM coverage focal LEFT JOIN disruption_annual annual
      ON focal.work_id = annual.work_id AND annual.age_year BETWEEN first_age AND least(last_age, focal.observed_age_end)
    GROUP BY focal.work_id, focal.publication_year, focal.reference_count_valid,
      focal.reference_list_unknown, focal.computation_status, focal.requested_age_start,
      focal.requested_age_end, focal.available, focal.is_mature, focal.observed_age_end
  ), scored AS (
    SELECT *, (NF - NB)::DOUBLE / nullif(NF + NB + NR, 0) AS disruption_cd_raw_observed,
      (NF - NB)::DOUBLE / nullif(NF + NB, 0) AS disruption_no_nr_raw_observed,
      citation_count - NF - NB AS citation_partition_delta,
      future_related_count - NF - NB - NR AS neighborhood_partition_delta
    FROM aggregated
  )
  SELECT *, DATE {literal(snapshot)} AS openalex_snapshot_date,
    CASE WHEN available AND is_mature AND reference_count_valid > 0 AND NOT reference_list_unknown
      THEN disruption_cd_raw_observed END AS disruption_cd,
    CASE WHEN available AND is_mature AND reference_count_valid > 0 AND NOT reference_list_unknown
      THEN disruption_no_nr_raw_observed END AS disruption_no_nr
  FROM scored
);
"""


CUSTOM_EXAMPLES = """SELECT * FROM disruption_age_range(1, 4);
SELECT * FROM disruption_age_range(1, 7);
SELECT * FROM disruption_age_range(2, 5);
SELECT * FROM disruption_age_range(0, 3);
SELECT * FROM disruption_age_range(0, 6);
"""


POLICY = """# Research convenience views v1

These views do not filter Works, rewrite counts, change scores or normalize fields.
Each research row remains one Work × window policy × window. Snapshot provenance
is attached as constants; the source manifests remain authoritative.

`disruption_work_wide` has one row per Work with both policies in column suffixes.
Its lifetime citation aliases explicitly name the policy; they are not graph_indegree_all.
The complete_calendar_years fields count calendar years fully ended by the snapshot,
from publication year or the following year respectively, independently of window size.
Unknown publication years yield NULL. These describe observation time, not index completeness.

Load custom_windows.sql after research_views.sql to register disruption_age_range.
custom_window_examples.sql shows exclude-year 4y and 7y, ages 2 through 5,
and include-year 4y and 7y. Counts cover only the observable intersection.
Missing annual rows become zero only with completed sparse coverage and an observable
start age. Entirely future, unknown-year or uncomputed ranges remain NULL.
A partially observed range retains counts but its interpreted score is NULL.
No graph scan is required; these lazy views/macros read annual/focal Parquet tables.
Full-range queries can still be large; add explicit focal Work selection when exploring.

`reference_count` aliases the strictly earlier-year effective reference count.
Reference thresholds retain SQL NULL when the count is unknown. Citation and
combined thresholds are NULL for uncomputed, unobservable or immature finite
windows. Lifetime remains usable when observed counts are available; it is not
declared immature merely because its is_mature field is NULL. Combined thresholds
are convenience policies, not mandated scientific inclusion criteria.

`has_valid_reference_graph` means that the focal year and reference list are known
and the recorded invalid-ID, dangling-ID and Work self-loop audit counts are zero.
Missing required audit counts yield NULL. Duplicate links are deduplicated and do
not make this flag false. Same-year, future-year and unknown-year reference audit
counts remain available in source_record_json; they are excluded from the strict
earlier-year reference set, but not added as new exclusions to this narrow flag.

`has_valid_citation_graph` is NULL when window counts cannot be computed; otherwise
it checks the independent citation partition invariant and that earlier-year and
unknown-year incoming audits are zero. A missing audit is unknown, not zero.
These narrow v1 checks cannot establish real-world bibliographic completeness,
causal ordering within a year or scientific suitability. No flag filters rows.

The retraction example expects a user-supplied `matched_retraction_works` relation
with Work URLs. DISTINCT prevents duplicate matches from multiplying rows.
Unmatched Works receive NULL metrics, not zero. Counts retain full-graph meaning.

The sidecar verifies manifest identity chains and the published SQL checksum;
it does not independently rehash every previously verified large graph or
Parquet artifact. Dataset-level checksum/coverage acceptance is a separate step.
"""


RETRACTION_SQL = """SELECT retractions.work_id, metrics.* EXCLUDE (work_id)
FROM (SELECT DISTINCT work_id FROM matched_retraction_works WHERE work_id IS NOT NULL) AS retractions
LEFT JOIN disruption_research_ready AS metrics USING (work_id);
"""


def generate(analytical_manifest, foundation_run, graph_manifest, destination):
    analytical_manifest, foundation_run, graph_manifest, destination = map(
        lambda path: Path(path).resolve(), (analytical_manifest, foundation_run, graph_manifest, destination))
    analytics = json.loads(analytical_manifest.read_text())
    foundation = json.loads(foundation_run.read_text())
    graph = json.loads(graph_manifest.read_text())
    if (analytics.get("complete") is not True or analytics.get("scope") != "all_graph_works"
            or foundation.get("status") != "complete" or graph.get("status") != "complete"):
        raise ValueError("All three source stages must be complete and analytics must cover all Works")
    foundation_link = analytics.get("config", {}).get("foundation", {}) or {}
    if (foundation_link.get("run_sha256") != digest_file(foundation_run)
            or foundation_link.get("path") != str(foundation_run.parent)):
        raise ValueError("Analytical foundation provenance mismatch")
    provenance = analytics.get("source_provenance", {})
    if provenance.get("graph_manifest_sha256") != digest_file(graph_manifest):
        raise ValueError("Analytical graph provenance mismatch")
    if graph.get("foundation_config_sha256") != foundation.get("config_sha256"):
        raise ValueError("Graph foundation configuration mismatch")
    snapshot = provenance.get("openalex_snapshot_date")
    if (snapshot != graph.get("snapshot_date")
            or snapshot != foundation.get("configuration", {}).get("snapshot_date")):
        raise ValueError("Snapshot dates differ")
    expected = analytics.get("focal_rows")
    if (type(expected) is not int or expected != foundation.get("rows")
            or expected != graph.get("node_count") or analytics.get("window_rows") != expected * 8):
        raise ValueError("Full-graph coverage counts differ")
    views = analytical_manifest.parent / "views.sql"
    if digest_file(views) != analytics.get("views_sha256"):
        raise ValueError("Published analytical SQL checksum mismatch")
    if destination.exists():
        raise FileExistsError("Immutable research sidecar already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        (temporary / "research_views.sql").write_text(render_sql(views.read_text(), snapshot,
            analytics["schema_version"], analytics["calculation_version"]))
        (temporary / "matched_retractions.sql").write_text(RETRACTION_SQL)
        (temporary / "custom_windows.sql").write_text(render_custom_windows(snapshot))
        (temporary / "custom_window_examples.sql").write_text(CUSTOM_EXAMPLES)
        (temporary / "POLICY.md").write_text(POLICY)
        outputs = {path.name: {"sha256": digest_file(path), "bytes": path.stat().st_size}
                   for path in temporary.iterdir()}
        result = {"complete": True, "version": VERSION, "generated_at": datetime.now(timezone.utc).isoformat(),
                  "code_sha256": digest_file(__file__), "snapshot_date": snapshot,
                  "sources": {name: {"path": str(path), "sha256": digest_file(path)}
                              for name, path in (("analytics", analytical_manifest), ("foundation", foundation_run), ("graph", graph_manifest))},
                  "outputs": outputs, "count_and_score_transformations": "none",
                  "validation_scope": "manifest_chain_and_source_sql_checksum"}
        (temporary / "manifest.json").write_text(json.dumps(result, indent=2))
        for path in temporary.iterdir():
            with path.open("rb") as stream:
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
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analytical_manifest", type=Path)
    parser.add_argument("foundation_run", type=Path)
    parser.add_argument("graph_manifest", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.analytical_manifest, args.foundation_run, args.graph_manifest, args.destination)))


if __name__ == "__main__":
    main()
