# Local OpenAlex snapshot validation

The offline implementation of [the analysis specification](OPENALEX_SNAPSHOT_ANALYSIS_SPEC.md)
validates the source, reconciles RW originals, screens document roles, calculates
descriptive statistics and selected publication denominators, and builds a separate
v3 report. The existing RW v2 report is preserved. Incoming citation edges have
a separate resumable scan; adjusted/causal research modules remain out of scope.

## Run

Python 3.11+ is required. Install the optional analytical dependencies separately
from the existing RW pipeline:

```bash
python -m pip install -r pipeline/snapshot_requirements.txt
export OPENALEX_SNAPSHOT_DIR=/mnt/hg02/openalex-snapshot/data/parquet
python -m pipeline.validate_snapshot \
  --output-dir /mnt/hg02/openalex-snapshot/analysis/validation \
  --scan-ids --check-remote --memory-limit 8GB --threads 4 \
  --accept-retrospective
```

The default without `--scan-ids` only inspects file metadata and cannot pass the
source gate. `--check-remote` retrieves only the small combined AWS manifest, not
another snapshot. All source reads use paths from the frozen combined manifest;
unlisted Parquet files are inventoried but never ingested. No API DOI subset is
used. The analytical engine projects IDs and flags and can spill to the external
output disk. This is an explicit offline command, not part of the website build
or weekly RW refresh.

Output is stored by manifest SHA-256 and validation start time. Each attempt keeps
the frozen manifest, per-entity manifests, per-file footer results, schema field
paths, and a `validation.json` report. The report records row/byte accounting,
identity uniqueness, null/boolean flag states, optional schema availability,
deletion-log availability, runtime, peak process RSS, and blockers. Schema
availability is not analytical readiness. An unavailable deletion log does not
authorize a survivor mapping.

Successful entity ID scans are checkpointed using the manifest hash, validator
version, configuration hash, listed file keys, schema fingerprints, sizes, and
nanosecond modification times. Only matching checkpoints are reused. Treat the
snapshot as immutable; delete its checkpoint directory if file modification
times were preserved during a content replacement. Footer checks and projected
column reads are not full content checksums or verification of every data page.

`latest-attempt.json` points to the last finished attempt. Only a completely
passing attempt updates `validated-source.json`. Failed/interrupted attempts
never replace the last validated-source pointer or any public report. Exit 0
means source validation passed; exit 2 means the persisted report lists blockers.

## Transfer provenance

The specification additionally requires a manifest captured before transfer and
retrieval timestamps. Downloading the latest AWS prefix and finding its manifest
unchanged afterward confirms current manifest agreement, but does not recreate
historical transfer evidence. Do not infer retrieval timestamps from partition
names, source timestamps copied by AWS, or the validator's start time.

If this evidence exists, supply `--transfer-provenance /external/transfer.json`:

```json
{
  "source_prefix": "s3://openalex/data/parquet/",
  "pre_transfer_manifest": "manifest-before-download.json",
  "manifest_captured_at": "<actual timezone-qualified ISO timestamp>",
  "retrieval_started_at": "<actual timezone-qualified ISO timestamp>",
  "retrieval_completed_at": "<actual timezone-qualified ISO timestamp>"
}
```

The manifest path is resolved relative to the provenance file. The placeholders
are documentation, not valid evidence. Without that evidence, the audit still
runs and preserves all results, but the strict specification's source gate stays
blocked. Changing to a retrospective acceptance policy requires an explicit
methodology decision; the validator does not silently waive it. On 2026-09-11 the
project owner explicitly accepted `retrospective-v1` for the existing AWS download.
`--accept-retrospective` records that policy while preserving missing historical
evidence. It does not waive remote-manifest, file, schema, or identity checks, and
does not accept contradictory transfer evidence.

## Tests

```bash
python -m unittest discover -s tests
```

Snapshot tests use synthetic Parquet fixtures. They cover manifest accounting,
unsafe/duplicate paths, unreadable files, missing files, ID ambiguity, null flags,
core/expansion separation, stale-file exclusion, checkpoint invalidation, transfer
evidence, and preservation of an earlier successful validation.
The verification workflow installs the analytical dependencies and runs these
fixtures. Environments with only the RW pipeline dependencies skip the snapshot
test module; the weekly RW refresh does not install or scan the snapshot.

## Analyze and build

Freeze an immutable RW input (the current run uses this commit):

```bash
python -m pipeline.fetch_rw_snapshot \
  --commit 6ddb2c80121ab22e5db8d3db0dd0fb4b9d348dfa \
  --output-dir /mnt/hg02/openalex-snapshot/analysis/rw
```

Read the report path in `validation/validated-source.json`, then run:

```bash
python -m pipeline.snapshot \
  --validation-report /absolute/path/to/validation.json \
  --rw-csv /mnt/hg02/openalex-snapshot/analysis/rw/retraction_watch.csv \
  --rw-source /mnt/hg02/openalex-snapshot/analysis/rw/source.json \
  --output-dir /mnt/hg02/openalex-snapshot/analysis/runs \
  --workers 8 --threads 6 --memory-limit 32GB
```

Memory is **per worker**: this setting allows up to 256 GB across eight independent
DuckDB connections, with up to 48 execution threads. Use smaller settings on a
smaller machine. Thread counts and memory limits are ceilings, not guaranteed
utilization; Parquet projection on a rotating disk may be I/O-bound. The scanner
prints its content-addressed run directory. Completed file checkpoints survive an
interruption; rerun the identical inputs and transformation to reuse them.

For a RAM-rich host with a rotating source disk, a sequential cache pass **before**
the analytical scan can reduce random reads:

```bash
python -m pipeline.warm_snapshot_cache --validation-report /absolute/path/to/validation.json
```

Run it separately, not concurrently with the disk-bound scans. In this session a
concurrent prefetch experiment caused disk contention and was stopped; warming
projected columns with the analytical workers paused reached approximately
160–190 MiB/s initially. The OS cache uses available RAM and remains evictable;
the command creates no second snapshot and does not prove full-file integrity.
For a resumed run, `--skip-completed-run "$RUN_DIR"` excludes completed main shards.

For the following commands, `RUN_DIR` denotes that external run directory:

```bash
python -m pipeline.snapshot_dimensions "$RUN_DIR" --workers 4 --threads 4 --memory-limit 16GB
python -m pipeline.snapshot_report "$RUN_DIR"
python -m pipeline.snapshot_citations "$RUN_DIR" --workers 6 --threads 8 --memory-limit 32GB
python -m pipeline.snapshot_supplement "$RUN_DIR" --workers 6 --threads 8 --memory-limit 32GB
python -m pipeline.snapshot_concepts "$RUN_DIR" --workers 6 --threads 8 --memory-limit 24GB
python -m pipeline.snapshot_taxonomy "$RUN_DIR" --workers 6 --threads 8 --memory-limit 32GB
python -m pipeline.snapshot_report "$RUN_DIR"
python -m pipeline.publish_snapshot "$RUN_DIR/report"
npm run build
```

The dimension pass may start while the main scan runs: it waits for each validated
work shard and uses its role evidence. It computes core article/review denominators
by publication year, primary Field, journal source, and both country modes. The
report checks that the Field partition, including unknown Field, reproduces the
original D exactly. Published denominator presets are intentionally finite.

All Parquet shards, RW originals/notices, candidates, and match records stay local.
`snapshot_report` refuses an incomplete full scan. It writes aggregate assets to
the local run directory; nothing is copied into `public/` until `publish_snapshot`
passes the independent v2/v3 schema checks, hash checks, exact path allowlist,
36-sample cap, and the combined 2 MiB budget. Publication atomically installs or
exchanges the snapshot directory. Linux `renameat2` is required to atomically
replace an existing directory; unsupported systems preserve the previous release.

The UI uses `#/snapshot/overview` and eight chapter routes. Its registry is the
manifest's exact `supported_slices`; unsupported URLs remain visibly unsupported.
Chapter fetches verify release IDs and SHA-256 and cancel outdated requests.
Country counting is a chart-local transform of already published cells; it does
not redistribute weights or create an uncomputed intersection. CSV exports carry
the selected metric, scope, release, dates, and methods.

## Interpretation and current limits

- A0 is flagged database records. A1/D applies the same corpus, type, date, and
  role exclusions. RW original/notice IDs override title heuristics; conflicts are
  quarantined. Default D excludes suspected notices, with same-scope inclusion
  sensitivity counts retained in the cohort export.
- Identifier matching searches flagged and nonflagged records. DOI/PMID ambiguity
  is preserved; there is no smallest-ID fallback or inferred survivor mapping.
- C can include RW events after the OA snapshot. Those descriptive views show the
  later RW cutoff. C_D rates require dated events no later than the OA snapshot.
- Raw RW reason labels and their per-original union are retained alongside exact
  project-defined families in `pipeline/reason_families.py`. The mapping is not
  an official RW taxonomy or an independent misconduct finding. Errors, concerns,
  source assertions, investigations, procedures and notice descriptors remain
  distinct. New labels become unmapped; absent labels become missing.
- Country association, association share, known-member fractional share, and cohort
  proportion have separate names. One observed country is never automatically
  called domestic; completeness remains unknown when the source cannot establish it.
- Concentration uses every positive-association entity, with unknown identities
  excluded; Top-k unique-paper unions are computed from IDs locally.
- Author-career inference, historical publisher responsibility and causal models
  are not inferred from static metadata. Current immediate/root publisher modes
  require journal sources and validated publisher IDs; broken/cyclic parent chains
  remain unknown. Source Work denominators, not publisher `works_count`, are used.

## Incoming citations and supplemental scans

The first report build persists validated matches needed by `snapshot_citations`.
It selects eligible core article C targets (including flag false/null), scans the
reference lists of **all** manifest-listed works, and writes unique citing/target
pairs locally. Source sizes/mtimes, transformation/input hashes, target hash and
output checksums protect resumable shard checkpoints. No incoming edges are public.
The separate supplemental pass reuses role evidence to compute OA-status, language,
observed-team and authorship-audit partitions. Every partition must reproduce the
existing full D and A1, including older publication years, before publication.

C2/C3/C4 exclude targets whose first RW event is later than the OA cutoff and report
that exclusion. Conflicting first dates across originals matched to one Work are
unavailable rather than selecting the earliest conflicting value. Same-day and
overlapping intervals are ambiguous. Missing dates and citing intervals extending
beyond the cutoff are undated. Reported day precision is not evidence of original
precision: C3 includes a sensitivity view expanding both dates to entire years.
The article/review citing sensitivity also excludes selected known/conflicting/
suspected notices; it is not a claim to identify every residual notice in the graph.

C2 uses complete per-target relative calendar-year windows with publication and
cutoff eligibility. C4 defaults to the identical five-year-complete target set for
all 1/3/5-year outcomes; separate window-specific cohorts are labeled independently.
Post-event windows exclude the event day and include the calendar anniversary day;
February 29 anniversaries clamp to February 28 in non-leap years. Coarse citing
intervals must fall wholly within a window, not be assigned by their start date.
Zero-edge targets remain in means, medians and coverage denominators. Static
`cited_by_count` disagreement is audited, not used as an event-ratio denominator.

Supplementary T3 fixed-publication-window proportions require a reported OA
publication day and complete calendar followup; valid RW events must fall between
publication and the relevant anniversary. These are RW-recorded proportions in an
OA-covered cohort, not universal fully observed risks. Missing publication dates
and short followup are explicitly combined in the exclusion count. Review strata
remain separate; the joined fixed-window presets are core article only.

The descriptive monthly control rule is pinned in
`data/reference/snapshot-burst-policy-v1.json`: a 24-complete-month baseline,
minimum 20, and threshold mean + 3√mean. It is an exploratory review rule, not a
calibrated significance test or prospective study preregistration. Missing months
mean no records in this frozen RW input, not proven historical absence.

Upstream semantics checked on 2026-09-11:
[resolved citation lists](https://help.openalex.org/data/works/citations/) and
[journal/publisher host organization](https://help.openalex.org/data/sources/attributes/).
The actual frozen Parquet schemas remain authoritative for this run.
