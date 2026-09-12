# OpenAlex Snapshot Retraction Analysis Specification

Version: 2.0 · Reviewed: 2026-09-10

**Status: implementation in progress.** The original S0 design has advanced to local source validation and analysis. Published RW statistics remain separate.

Implementation progress (2026-09-11): the retrospective source gate, S1/S2 report,
incoming-edge scan, fixed-window citation summaries, versioned reason families,
current publisher rollups and supplementary denominators are implemented.
Capabilities are promoted only after numerical and publication gates pass; see
the [runbook](OPENALEX_SNAPSHOT_RUNBOOK.md) and generated manifest. Optional
adjusted/causal models and historical ownership research are not implied by S3.
The normative requirements below remain in force.

Source acceptance amendment (2026-09-11, explicitly approved by the project owner):
the existing AWS download may use **retrospective-v1** validation because a
pre-transfer manifest and retrieval log were not retained. This exception requires
a frozen local manifest, agreement with the current AWS manifest after validation,
complete listed-file size/footer/row/schema checks, and canonical ID/flag checks.
Record historical transfer provenance as missing; do not invent retrieval dates
or claim an atomic historical transfer. All other source and publication gates
remain in force. `strict-v1` remains available for future documented transfers.

Companion: [Website Report Design](WEBSITE_REPORT_DESIGN.md). Existing production methodology: [RESEARCH.md](RESEARCH.md).

Candidate-scope amendment (2026-09-12, explicitly approved by the project owner):
`original-first-independent-notices-v2` supersedes the article-only and automatic
title/type/conflict exclusions below for runs declaring this policy. Retain core
Works of all types under the same valid-date boundary. Exclude a notice only when
its RW identifier relationship points to a different comparable original DOI/PMID
and the Work does not itself match original identifiers. Preserve uncertainty;
retained Works are candidates, not independently confirmed original papers.
Recompute publication denominators and every dependent analysis under the same
policy; do not divide broad numerators by legacy article-only denominators.
Explicit article/review comparison slices remain narrower and labeled. Identifier
ambiguity and contradictory DOI/PMID matches remain unresolved, not arbitrarily
selected. Source snapshots and historical runs remain unchanged. See
[policy review and validation](BROAD_WORK_POLICY_REVIEW.md) for provenance,
recomputed totals, reassessed examples and acceptance evidence.

## 1. Scope and review decisions

Preserve the current RW-only report. The existing limited OpenAlex DOI lookup is a debugging/enrichment subset, not a representative analytical sample. The snapshot phase is a separate, versioned report; it must not silently replace the current population, taxonomy, or observations.

The review of the previous specification found the following issues. These decisions are normative for the new phase.

| ID | Issue | Required correction |
|---|---|---|
| R01 | Every `is_retracted=true` work was effectively treated as an original paper | Separate flagged database records, original-paper candidates, and known notices; audit document role before rate publication |
| R02 | Two datasets could be read as independent validation sources | OpenAlex documents its retraction flag as RW-derived; report reconciliation and enrichment, not independent confirmation [S2] |
| R03 | Snapshot/API corpus differences were not operationalized | Freeze `core`, `expansion`, and `all` using `is_xpac`; never mix them in rates [S1] |
| R04 | Country attribution assumed all countries require resolved institutions | Preserve strict institution-derived and broader authorship-country modes separately [S3] |
| R05 | One observed country implied domestic collaboration | Introduce incomplete/unknown affiliation states and audit truncated author lists |
| R06 | A single definition of share hid alternative denominators | Separate paper coverage, association share, fractional share, and cohort proportion |
| R07 | DOI ambiguity and redirects were underspecified | Match original identifiers against all eligible OA works; quarantine ambiguous matches; never assume a redirect or choose the smallest ID |
| R08 | Snapshot cutoffs and fixed follow-up windows were underspecified | Separate status-at-snapshot from dated RW events; specify common-cutoff and follow-up eligibility |
| R09 | Concentration could double-count overlapping papers | Distinguish association concentration from unique-paper coverage of a selected entity set |
| R10 | Citation totals were insufficient for event-time analysis | Require incoming citation edges, date precision, ambiguous-date bins, and follow-up denominators |
| R11 | New JSON paths conflict with the current deployment guard | Define a versioned asset/schema migration, retaining raw-data prohibitions and the compact-data budget |
| R12 | Website requirements stopped at generic chart principles | Add a chart catalogue, explanatory narrative contract, supported filters, failure states, and visual acceptance criteria |

The repository's `data/reference/openalex-audit.json`, checked on 2026-09-09, already records a notice classified as `article`. Its stored counts are historical API observations, not new snapshot results or constants to copy into charts. Removing only `type=retraction` is therefore not a sufficient original-paper screen.

## 2. Source responsibilities and dependence

**Retraction Watch (RW)** supplies original-paper identifiers, notice identifiers, dates, reasons, subjects, and recorded author/affiliation/venue strings. Its CSV also contains other notice categories; those are not equally comprehensive [S4]. Preserve the original-paper/notice distinction throughout ingestion.

**OpenAlex (OA)** supplies the scholarly graph, standardized entity associations, classification, and publication denominators. Its `is_retracted` field is documented as based on RW [S2]. Agreement measures metadata propagation/coverage and matching consistency, not two independent detections of retraction.

**Joined RW × OA** supports reason–topic, event lag, and citation-persistence analyses. Matching success does not demonstrate correct author disambiguation, accurate affiliation, or independently verified retraction status.

Keep RW Subject, OA Topic hierarchy, and legacy Concepts as separate systems. Do not infer that RW raw author and affiliation lists are aligned by position; the RW guide explicitly warns against that inference [S5].

## 3. Snapshot completion and schema gate

The complete intended Parquet download must pass the source gate before the new phase runs. Do not download both formats or ingest the legacy prefix as an additional population.

Current documented Parquet prefix: `s3://openalex/data/parquet/`. Current snapshots provide combined and per-entity manifests; records are partitioned by update date, not publication or retraction date. The current manifest/schema, rather than a hard-coded historical directory list, is the authority [S1].

Required procedure:

1. Record the intended source prefix, release date, retrieval start/end, and a frozen copy/hash of the source manifest before ingestion.
2. Enumerate the files from that manifest. Check presence, sizes, Parquet readability, schema, and row counts; do not treat successful `aws s3 sync` exit alone as analytical validation.
3. Compare the source manifest again after transfer. A changing public prefix is not automatically an atomic snapshot. Reconcile to a single manifest generation before proceeding.
4. Exclude stale/unlisted local partitions from ingestion. Never use an unrestricted glob over multiple snapshots or formats.
5. Validate canonical ID uniqueness and boolean/null semantics of `is_retracted` and `is_xpac`. Unexpected duplicate IDs block canonicalization until explained; do not hide them with arbitrary deduplication.
6. Record deletion-log availability and schema. Current documentation says deleted/merged-away IDs can return 404, not a survivor redirect [S6]. A deletion record alone does not identify a replacement.
7. Persist a source-validation report. Local checksums establish local reproducibility; an S3 ETag must not be assumed to be a file MD5. Footer/row-count checks are not a cryptographic proof of content integrity.

Core capabilities require works and their identifiers, flags, dates, types, affiliations, and classifications. Entity dictionaries enrich labels and identities. Citation, publisher, author-career, and optional funding features get separate capability gates after the overall download gate passes. A missing optional field disables its dependent feature rather than fabricating values.

Inspect actual nested Parquet schemas before writing adapters. Record detected field paths/types and adapter version. Do not assume every entity, field, or API-derived attribute exists in every release.

## 4. Canonical entities, document roles, and analysis populations

### 4.1 Canonical records

Maintain separate logical tables:

- `oa_work`: one record per valid snapshot Work ID, raw provenance retained.
- `rw_original`: one deduplicated original-paper record, retaining all contributing RW record IDs.
- `rw_notice`: notice records/identifiers, nature, date, and source reasons; duplicate source rows are not automatically distinct events.
- `work_notice_link`: original-to-notice relation and evidence.
- `rw_oa_match`: candidates, selected match, evidence, ambiguity, and reconciliation state.
- `work_entity_bridge`: deduplicated work–author/institution/country/topic/source associations and counting weights.
- `citation_edge`: unique citing-work/target-work pairs for the selected targets; local only.

A work may have several notices; a bulk notice may refer to many originals. Keep both relations. Do not automatically merge a preprint with a version-of-record article or combine different DOIs just because titles resemble each other.

### 4.2 Document-role policy

Maintain `document_role` and `role_evidence`: `original_supported`, `known_notice`, `suspected_notice`, `unresolved`, or `conflict`.

Use original and notice identifiers in RW, explicit structured notice relations when available, and work type as auditable evidence. If one identifier appears in conflicting roles, quarantine it. Title patterns generate review candidates only; a title containing “retraction” is not sufficient evidence for deletion.

For analytical publication candidates, apply the same role policy to all denominator and numerator works. Known notices and unresolved role conflicts are excluded. Suspected notices require adjudication or an explicitly published exclusion/inclusion sensitivity analysis. `unresolved` means not independently confirmed as an original; never relabel it as confirmed merely because it is typed `article`.

### 4.3 Populations

| Key | Definition | Permitted interpretation |
|---|---|---|
| A0 | All unique OA records with `is_retracted=true`, within an explicit corpus | Flagged Work records; diagnostic total, not original-paper total |
| D | All eligible publication candidates after corpus/type/date/document-role rules | Denominator corpus |
| A1 | `A0 ∩ D` | Flagged publication candidates after documented screening |
| B | RW Retraction-category deduplicated originals under the current RW methodology | RW-recorded original papers, not all historical retraction events |
| C | High-confidence links from B to OA works, regardless of the OA flag | Matched/enriched RW population; may include OA flag false or missing |
| C_D | `C ∩ D` with the required date cutoff for a particular metric | RW-recorded numerator inside the OA publication corpus |

C is not necessarily a subset of A0. Matching only against flagged OA records would conceal RW originals whose flag has not propagated.

Other RW notice categories remain available for quality/event context but are not added to B. A current-state CSV is not a complete longitudinal state-transition log: do not claim complete correction → concern → retraction → reinstatement histories.

## 5. Corpus, cutoffs, and eligible works

Record `oa_snapshot_date`, `rw_snapshot_date`, and `metric_observation_cutoff` independently. Never assign a date to an OA flag using `created_date`, `updated_date`, or a partition name.

For the first snapshot release:

- Default publication corpus: **core** (`is_xpac=false`). Publish `expansion` and `all` as separate diagnostics/sensitivity views only when validated. Missing corpus flags are audited, not silently treated as core.
- Default work type: `article`; `review` is a separate stratum. A combined article/review view requires an explicit combined denominator. Future types are discovered from the pinned vocabulary [S7].
- Default trend presentation begins in 2000; this is a display range, not permission to drop older works from source accounting. Each rate identifies its exact publication-year cohort/range.
- Rates use publication cohorts; notice-year filters do not apply to the publication denominator.
- For A1/D, observation is OA status at the OA snapshot. This cannot reconstruct status at an arbitrary earlier date.
- For C_D/D, restrict RW events to an explicitly declared cutoff no later than the relevant OA snapshot for snapshot-aligned comparisons. Retain later RW events in a separate, visibly later-dated enrichment view.
- For fixed 1/3/5-year outcomes, require dated events and complete elapsed follow-up through the declared cutoff. Call the result an **RW-recorded fixed-window proportion in an OA-covered cohort**, not a fully observed universal risk.

A recent cohort's lower observed proportion is not evidence of improvement. Older cohorts have longer opportunity for retraction. Cross-year causal or risk comparisons require an additional censoring/standardization design.

## 6. Metric dictionary: counts, shares, and proportions

Let P be the unique works in a chart's declared population and filter scope; `G(w)` its distinct observed members of the active dimension. Define full count `n_g = Σ_w 1[g ∈ G(w)]` and, for known-member fractional mode, `f_g = Σ_w 1[g ∈ G(w)] / |G(w)|` over nonempty sets.

| Metric ID | Formula | Meaning / invariant |
|---|---|---|
| `work_count` | `|P|` | Unique works, not source rows or notices |
| `linked_work_count` | `n_g` | One contribution per work per distinct member |
| `paper_coverage_pct` | `100 * n_g / |P|` | Percentage of papers linked to g; sums may exceed 100% |
| `association_share_pct` | `100 * n_g / Σ_h n_h` | Share of all member–paper associations; sums to 100% over included known members |
| `fractional_work_count` | `f_g` | Work-equivalent allocation, not number of physical papers |
| `fractional_share_pct` | `100 * f_g / N_known` | Sums to 100% over known members under known-only allocation |
| `oa_flagged_cohort_per_10k` | `10000 * |A1_g| / |D_g|` | Observed flag-based cohort proportion after role screening |
| `rw_recorded_cohort_per_10k` | `10000 * |C_D,g| / |D_g|` | RW-recorded events linked into the OA-covered cohort |
| `annual_count_yoy_pct` | `100 * (R_t-R_(t-1))/R_(t-1)` | Growth in counts, not growth in individual misconduct risk |

Choose an explicit share metric in UI and exports; never expose an unqualified `share` or `占比`. Top-N display does not change the denominator to Top-N unless explicitly labeled.

Fractional rates are separately named weighted proportions: apply identical per-work dimension weights and eligible scope on both sides. Weights are set before a member display filter; selecting one country must not reallocate the paper's weight to it. Quantiles and unique-paper unions are not additive.

Compute denominators from canonical works, not entity-level `works_count` or `counts_by_year`, which are convenience summaries and may have different refresh periods/scope [S8].

Release safeguards (project policy, not scientific laws): show n/N for every rate; do not rank rates unless N ≥ 1,000 and numerator ≥ 20; mark count-growth baselines below 20; a prior count of zero gives undefined growth, not infinity. Keep all groups in an explanatory table, including valid zeros, while marking groups ineligible for ranking. Thresholds are versioned configuration.

The census of a snapshot has no sampling uncertainty about its stored counts. Optional binomial intervals must be labeled model-based reference intervals, not coverage/misclassification uncertainty. Do not apply ordinary binomial intervals to fractional weights or pretend such intervals resolve source bias. `null`, zero, unknown, small-base, and not-computed are different states.

## 7. Country attribution and affiliation completeness

Country refers to the location associated with an authorship on that work, **not nationality, citizenship, residence, funding origin, or an intrinsic paper country**.

Store separate sets:

- `institution_country_codes`: countries of distinct resolved work-level institutions; default, preserving the previously agreed institution-linked interpretation.
- `authorship_country_codes`: union of OA authorship `countries`; this can include address-derived countries without a resolved institution [S3].
- `rw_country_labels`: RW's recorded affiliation/reliable-source country labels, kept as a separate source view [S5].

Keep provenance, set differences, unresolved affiliation counts, and a `country_attribution_mode` in each chart. Do not silently union the two OA modes or borrow a current author's `last_known_institutions` to classify an old paper.

Full counting deduplicates countries within a work. CN, CN, US yields CN +1 and US +1. First-author and corresponding-author views are optional: each can have multiple countries or missing data. Neither establishes leadership or responsibility. RW list order cannot identify first-author institutions.

For new OA-country fractional statistics, distribute weight equally over distinct known countries; wholly unknown papers form a separate missingness count. Publish that known-only allocation can over-credit observed countries on partially observed papers. An equal-author sensitivity rule requires within-author multi-affiliation splitting and its own name; it is not measured contribution.

Classify collaboration as:

- `multi_country_observed`: at least two known countries; observed lower bound, even when incomplete;
- `single_country_complete_observed`: exactly one known country and no detected missing/truncated authorship-country coverage;
- `single_country_incomplete`: one country plus unresolved/truncated/uncertain coverage;
- `country_unknown`: no usable country;
- `completeness_unknown`: source does not permit a defensible completeness judgment.

Do not call all one-country rows “domestic.” Bilateral and 3+ bands describe **observed** country counts. Source documentation describes author-list caps in some representations; inspect the actual snapshot, stored counts, and flags rather than assuming every list is complete [S3].

## 8. Institutions, authors, sources, and publishers

Use deduplicated work-level IDs, while retaining raw source strings. Do not merge real entities based only on display names.

**Institutions:** default to directly attached institutions. Parent/lineage rollups are a separate mode; do not add a hospital and its parent university twice at the same reporting level. Unknown/unavailable placeholders are normalized by exact rules and shown outside Top-N real-entity rankings. The current RW rule that retains one unknown group alongside known institutions remains unchanged; new OA known-only fractional weights must be labeled differently rather than silently changing old RW results.

**Authors:** OA IDs reduce but do not eliminate split/merge ambiguity [S9]. Exclude null/deleted placeholder identities from named rankings and network centrality, while reporting their coverage. Repeat bands are 1, 2, 3–5, 6–10, and >10 unique linked works. Prefer aggregate distributions over public accusatory lists. Earliest indexed publication is not proven career start; derive it from works, not a short recent-year summary. Career-age analyses are optional and coverage-limited.

**Sources:** default venue is the primary publication source. Do not count all repository locations as separate journals. A journal-only analysis requires a journal-source filter on numerator and denominator. Preserve missing-source and non-journal states.

**Publishers:** use the source's host organization and validate whether it is a publisher rather than a repository's institution [S10]. Immediate publisher and parent group are different rollups. Current ownership is not necessarily ownership at publication or retraction; label snapshot-based publisher assignment. Historical responsibility requires dated ownership evidence, not the current entity record.

**OA status and language:** use the pinned work-level vocabulary, preserving unknown/new values. OA status is snapshot status, not necessarily access at publication; RW notice paywall status is not original-paper OA status. Metadata language is not automatically full-text language [S2].

## 9. Disciplines and additional dimensions

RW Subject retains its official two-level prefix/label display. OA uses Domain → Field → Subfield → Topic. No synthetic RW-to-OA equivalence or Concept-to-Topic ladder is allowed.

Primary-topic mode gives one path per classified work. Any-topic mode counts each distinct topic and deduplicates parents separately. In any-topic mode, sum of child full counts can exceed the parent's unique-paper count. Equal-member fractional weights recomputed independently at each level need not add from child to parent. An additive hierarchy chart must therefore use primary-topic mode or a separately defined leaf-conserving allocation.

Topic scores are not author contribution weights or calibrated retraction probabilities. Assigned topic breadth is an annotation-based proxy, not a complete measure of interdisciplinarity. Concepts are frozen legacy classification and unsuitable for unqualified current-year trend claims [S11].

Analysis catalogue:

| Dimension | Core measures | Additional requirement |
|---|---|---|
| Publication cohort | Counts, observed cohort proportions | Common corpus and follow-up explanation |
| RW event year | First recorded retraction counts | Valid original/notice relationship and dates |
| Subject / OA hierarchy | Counts, year heatmaps, rates where eligible | Separate taxonomies and attribution modes |
| Reason | Multi-label prevalence, co-occurrence | Versioned raw-to-family mapping |
| Institution / author | Linked works, repetition, concentration | Identity/missingness audit |
| Country / collaboration | Linked works, rates, cooperation matrix | Country mode and completeness strata |
| Source / publisher | Counts, rates, dated bursts | Primary venue, ownership basis |
| Work type / OA status | Counts and matched-scope proportions | Actual schema vocabulary; snapshot semantics |
| Team size | Counts, distribution, proportion by band | Observed/truncated author-list status |
| Citation impact | Zero share, median, percentiles, ECDF | Citation availability and publication-age comparison |
| Citation persistence | Before/after/ambiguous edges; fixed windows | Full incoming-edge scan and reliable event dates |
| Funding / MeSH / SDG / keywords | Optional exploratory association views | Actual fields, source-specific coverage, no claim of comprehensive coverage |

Optional dimensions must not become default risk rankings merely because fields exist.

## 10. Dates, event lag, and reasons

Preserve raw dates, parsed dates, precision, source, and conflict flags. For OA publication cohorts use the pinned OA publication year. For RW-only lag keep the existing RW date rule; joined lag uses valid RW original date by default, a tagged OA fallback when absent, and a sensitivity comparison for conflicts. Do not automatically choose the earliest date across unrelated versions/sources.

Lag is first valid recorded retraction date minus the chosen original publication date. Store days; display days/365.25 as years. Exclude negative/invalid lag from valid-lag plots without deleting the work. Use explicit half-open bands: [0,1), [1,2), [2,5), [5,10), [10,∞) years. Publish sample n and date exclusions beside P25/P50/P75/P90 and ECDF.

Coarse/uncertain dates become intervals, not invented January 1 event dates. A complete-looking source date does not prove original precision. Document precision uncertainty where unrecoverable. Lag distributions condition on recorded retraction; they are not survival probabilities for all papers.

Keep raw RW reasons and a versioned many-label family mapping. Separate substantive reasons from notice/procedure descriptors. Do not collapse allegations, investigations, honest errors, and confirmed misconduct into an undifferentiated integrity verdict. Multi-label prevalence can exceed 100% in total.

Default reason-by-paper statistics use the union of deduplicated reasons across that paper's included Retraction records and say so. Event-level analyses retain event-specific reasons. Linking a union to the first date does not prove every reason was known on that date. Unknown/unmapped labels remain visible and do not disappear from quality reporting.

## 11. Matching and reconciliation

Normalize DOI resolver prefixes, casing, whitespace, and URL encoding conservatively; keep the raw value. Recognize placeholder strings; do not strip arbitrary DOI suffix punctuation without evidence. PMID has its own validated namespace.

Match **RW OriginalPaperDOI**, not the notice DOI, against canonical OA works. Exact PMID or another validated identifier may support a match where DOI is absent. Contradictory identifiers block automatic selection. Ambiguous one-to-many candidates stay ambiguous; no lexicographic-ID fallback from the old debug pipeline is allowed in this phase.

Use explicit fields rather than one overloaded status:

- `match_method`: exact_doi / exact_pmid / other_validated_id / none;
- `match_outcome`: unique / ambiguous / conflicting / unmatched;
- `oa_record_state`: present / deleted / absent / survivor_mapping_verified;
- `oa_retracted_flag`: true / false / null;
- `original_notice_role` and supporting evidence.

Resolve survivors only from an actual documented mapping, preserving the old/new ID and mapping provenance. Never infer a merge target from an HTTP 404 or similar title [S6].

Publish a reconciliation matrix separating RW-matched/OA-flag-true, RW-matched/OA-flag-false, RW-matched/flag-missing, RW-unmatched, and OA-flagged-without-RW-match. Include ID availability and role-screening exclusions. Report both DOI-conditional match coverage and coverage of all RW originals.

Stratify missingness/matching by publication era, RW Subject, recorded country, and work type where available; use raw RW fields for unmatched records rather than inventing OA classifications. There is no assumption that unmatched records are random. Reconciliation is not precision/recall without an independently audited reference set.

## 12. Citation impact and persistence

Static `cited_by_count` is a snapshot summary. Distinguish zero citations from unavailable data, include zeroes in distributions, and avoid comparing old and recent works as though they had equal citation opportunity.

For event-time analysis, scanning only retracted works' references finds their **outgoing** references, not incoming citations. Build the retracted-target ID set, scan referencing works, and retain distinct `(citing_work_id, target_original_work_id)` edges. The graph is based on resolved reference lists [S12]. Report the citing corpus; default to all validated snapshot works for coverage, with publication-type/notice sensitivity filters explicitly named.

Classify each edge using citing publication date as a citation-time proxy:

- definitely before: citing-date interval ends before retraction-date interval begins;
- definitely after: citing-date interval begins after retraction-date interval ends;
- ambiguous: intervals overlap, including same-day dates at day precision;
- undated: a required date is absent/unusable.

Default `post_retraction_citation_ratio = after / (before + after)`, explicitly a ratio among temporally classifiable observed citation edges. Publish ambiguous and undated counts separately. Do not divide by `cited_by_count` and assume it exactly equals the rebuilt edge count; audit differences. No dated edges gives null, not zero.

For 1/3/5-year persistence, require complete post-event follow-up and use per-work calendar windows. Publish both total edges and mean/median per eligible target, plus eligible-target counts. Do not average ratios with inconsistent weights or compare unaligned windows. Separate before/after describing patterns from causal claims about retraction's effect.

A citation may criticize or report the retraction. No citation sentiment or endorsement claim is allowed without separately validated context analysis. Self-citation exclusion is optional and depends on valid author IDs; uncertain identity is not a confirmed non-self-citation.

## 13. Concentration, bursts, and advanced inference

For entity weights `x_g`, association concentration uses `s_g = x_g / Σ_h x_h`; specify full or fractional weights and whether entities with zero retracted works are included. Compute Top-k shares, Lorenz/Gini, or HHI over the full eligible entity distribution, **not only the exported Top-N rows**. Unknown placeholders are coverage, not a real institution/author.

Unique-paper coverage of Top-k entities is a separate statistic: `|union of linked paper IDs| / |P|`. Shared authorship means summing author counts is not this union. An entity's presence in a co-retraction network is not proof of collaboration in misconduct.

Burst detection requires actual RW event dates, not OA update dates. Pre-register window, historical baseline, minimum count, threshold, and handling of missing months. A recommended first implementation is a descriptive monthly control chart with flagged windows requiring review; do not infer paper-mill causes from a spike alone. External event annotations need an explicit source and event date.

Survival analysis, adjusted comparisons, matched controls, and multivariable models are later research modules. They require non-retracted eligible works, censoring, selection-bias discussion, and a separately reviewed analysis protocol. A convenience API flag and a case-only lag distribution do not identify a causal risk model.

## 14. Offline pipeline and resumability

Planned stages, not existing commands:

1. `validate_snapshot`: freeze manifest and schema/capability report.
2. `canonicalize_works`: source accounting, identity checks, corpus flags, minimal projected columns.
3. `canonicalize_rw`: originals, notices, role evidence, dates and reason mapping.
4. `reconcile_identifiers`: join against all relevant OA records; adjudication queue.
5. `build_eligible_corpus`: D, A0, A1, C, C_D and dimension bridges.
6. `aggregate_denominators`: publication cohorts and supported dimension slices.
7. `aggregate_descriptive`: counts, proportions, distributions, missingness, concentration.
8. `scan_incoming_citations`: optional separate pass with target-ID filtering.
9. `build_report`: compact chart payloads, deterministic observations, provenance.
10. `validate_and_publish`: numerical/schema/asset gates, then an atomic report release.

Use a local analytical engine capable of Parquet projection and disk spill; DuckDB is a candidate, not a required untested performance promise. Benchmark a pinned subset, record runtime/memory/disk, and choose partition work units. No full Python list of all works or quadratic join is acceptable.

Checkpoint by input manifest hash, file key, transformation version, and config hash. Only a matching checkpoint is reusable. Use temporary outputs and atomic rename; interrupted stages must not replace the last successful report. Full source scans happen locally, not during a normal Cloudflare build or weekly RW refresh.

Prefer raw snapshot storage outside the repository via `OPENALEX_SNAPSHOT_DIR`. If an in-repo local path is later supported, add an explicit ignore rule before using it; the previous recommendation of `data/local/` did not itself make that path ignored. Intermediate full records remain private/local and never become site assets.

## 15. Report data contract and deployment migration

Current production uses schema v2, `public/data/report.json`, `public/data/samples.json`, a maximum of 36 samples, and a 2 MiB combined data budget. `scripts/check-public-data.mjs` hard-codes that allowlist and RW-only schema assertions. None of those guards is changed by this documentation commit.

The implementation must introduce a reviewed v3 contract and exact path allowlist before adding report chunks. See the companion design for the proposed manifest/section layout. Retain v2 read support and the existing RW report. Test v2 and v3 independently; do not merely delete the old assertions or permit arbitrary JSON under `public/`.

Keep all published aggregate JSON and display samples combined within **2 MiB**, including coexistence with v2. Sample limit remains **36 across the deployed site**, not 36 per page. If the proposed views exceed the budget, reduce dimensions/presets or export precision; any budget change needs a separate explicit decision. Do not commit raw CSV, Parquet, JSONL, Gzip partitions, local databases, or full per-paper/author-network exports. User-generated CSV exports contain only already published aggregate cells and their metadata.

Every chart payload needs: chart ID, release ID, population key, metric ID, corpus/type scope, attribution policy, filters, both source dates/cutoff, numerator/denominator, missingness, status, and methods version. Source changes must not silently alter the chart's meaning.

## 16. Provenance and report status

Manifest fields include:

```json
{
  "schema_version": 3,
  "release_id": null,
  "status": "awaiting_snapshot",
  "oa_snapshot_date": null,
  "oa_source_prefix": "s3://openalex/data/parquet/",
  "oa_manifest_sha256": null,
  "rw_snapshot_date": null,
  "rw_source_commit": null,
  "rw_csv_sha256": null,
  "pipeline_commit": null,
  "config_sha256": null,
  "schema_adapter_version": null,
  "role_policy_version": null,
  "reason_mapping_version": null,
  "country_attribution_mode": "institution_country",
  "corpus": "core",
  "metric_observation_cutoff": null,
  "generated_at": null,
  "capabilities": {},
  "source_accounting": {},
  "quality_gates": {}
}
```

The nulls above are a schema illustration, not a generated result. Production ready reports must satisfy the required non-null fields. Waiting, unavailable, suppressed, and computed-zero states are different and must remain different in JSON and UI.

## 17. Required tests and publication gates

The following are acceptance requirements, not tests claimed to have been implemented by this spec.

| Test | Required outcome |
|---|---|
| Same paper, two notices | Original count 1; notice records and first-date policy retained |
| Bulk notice, several papers | Do not merge originals by common notice DOI |
| Notice typed article | Role screen catches known notice; residual uncertainty reported |
| Duplicate DOI, multiple OA IDs | Ambiguous queue, no arbitrary ID selection |
| Original exists, OA flag false | Included in C reconciliation, not A0 |
| Deleted ID without mapping | No invented surviving ID |
| Core vs expansion | Disjoint partitions with explicit unknown handling; comparable numerator/denominator |
| Paper with CN, CN, US | Full counts CN=1, US=1; fractional CN=0.5, US=0.5 |
| Country from raw address only | Present in authorship-country mode, absent from strict institution mode |
| One known country plus missing affiliations | Not automatically classified as domestic |
| Two topics sharing a parent | Parent full count deduplicated; hierarchy chart mode validated |
| Select a single member | Fractional weight unchanged; no hidden reallocation |
| Two authors on the same retracted paper | Association counts sum to 2; their union covers 1 paper |
| No denominator / zero denominator | Rate null with reason; never zero or infinity |
| Zero numerator, valid denominator | Valid zero, with n/N and ranking eligibility |
| Undefined growth / partial year | Correct null/partial state, no improvement headline |
| Coarse date / same-day citation | Ambiguous bin, not arbitrarily before or after |
| Short post-retraction follow-up | Excluded from longer fixed-window metric, counted in exclusions |
| Weighted metric / quantile reaggregation | No ordinary binomial CI for weights; no average of medians |
| Changed filters | Chart, observations, provenance, exported data update together |
| Raw asset or excessive samples | Build fails |
| Incomplete generation | Last validated release survives unchanged |

Source accounting must reconcile input records, unique IDs, role exclusions, eligible cohorts, matched/unmatched rows, missing dates, and flag states. For each full-count rate assert numerator is a subset of denominator; for weighted rates additionally validate weight equality. Test quantitative invariants before visual acceptance.

## 18. Delivery phases and definition of done

**S0 — review/design:** this document and the website report design only. No new counts or public conclusions.

**S1 — validated descriptive report:** snapshot/source gate; document-role screening; A0/B/C reconciliation; publication and RW event trends; classification, affiliation, entity, reason, lag, and quality panels with exact population labels. Every visible principal chart includes numerical observation and interpretation boundaries. Unsupported modules remain unavailable, not filled with samples.

**S2 — denominator and joined report:** D validated; at least one documented article-cohort proportion; rate-size comparisons; Reason × Topic; observed collaboration; complete concentration calculations. Review data coverage and the meaning of each denominator before promotion.

**S3 — citation and advanced modules:** incoming-edge pipeline, fixed-window persistence and optional burst/network research. A lack of citation readiness must not be disguised as zero citations or prevent a correctly labeled S1 release.

The phase is done only when the promised ready capabilities, reproducible manifests, numerical gates, compact deployment, and the companion design's narrative/interaction/accessibility tests pass. Do not claim all later modules complete merely because S1 can be deployed.

## 19. Official references and review context

References checked on 2026-09-10. Upstream behavior can change; the actual downloaded release and recorded adapter remain authoritative. These are sources for factual field/format definitions, not endorsements of this project's proposed statistical policies.

- [S1 — OpenAlex snapshot format and corpus differences](https://help.openalex.org/access/snapshot/)
- [S2 — OpenAlex work attributes, including retraction provenance](https://help.openalex.org/data/works/attributes/)
- [S3 — OpenAlex authorships, countries and completeness](https://help.openalex.org/data/authorships/)
- [S4 — Crossref Retraction Watch access and coverage](https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/)
- [S5 — RW field definitions](https://retractionwatch.com/retraction-watch-database-user-guide/retraction-watch-database-user-guide-appendix-a-fields/)
- [S6 — OpenAlex synchronization, deletions and merges](https://help.openalex.org/access/sync/)
- [S7 — OpenAlex work-type vocabulary](https://help.openalex.org/data/work-types/)
- [S8 — OpenAlex counting and cached entity summaries](https://help.openalex.org/how-to/counting/)
- [S9 — OpenAlex author identity and derived profiles](https://help.openalex.org/data/authors/)
- [S10 — OpenAlex source attributes](https://help.openalex.org/data/sources/attributes/)
- [S11 — OpenAlex legacy Concepts](https://help.openalex.org/data/concepts/)
- [S12 — OpenAlex citation graph](https://help.openalex.org/data/works/citations/)

Repository review baseline: `4513bd2b6ffe01676788da517dd3e73340aa6efb`. Inspected the previous snapshot spec, README, current React report components, public-data guard, and stored OA audit. Historical v2 statistics and their methodology are not re-estimated by this revision.
