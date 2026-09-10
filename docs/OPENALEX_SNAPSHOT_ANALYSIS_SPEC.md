# OpenAlex Snapshot Retraction Analysis Specification

Status: Planned — execution starts only after the full OpenAlex Parquet snapshot download and integrity checks complete.

## 1. Purpose

This document specifies the next-stage retraction analysis for **Scholarly Retraction Observatory** using a full OpenAlex snapshot, with Retraction Watch (RW) retained as an independent retraction-event dataset.

The current `docs/RESEARCH.md` analysis remains unchanged: it uses Retraction Watch as its primary corpus and treats the existing limited OpenAlex DOI lookup only as cross-validation. The analysis defined here is a **new phase** and must not silently replace, merge into, or reinterpret the current RW-only statistics.

The new phase begins only when:

1. the intended OpenAlex Parquet snapshot has downloaded successfully;
2. all required entity directories/manifests are present;
3. file integrity/basic row-count checks pass;
4. the snapshot date/version is recorded;
5. the pipeline can reproduce the same source counts from a clean run.

Until those conditions are met, no OpenAlex-derived global retraction rate, country rate, institution rate, field rate, author rate, or citation analysis should be published as a completed result.

---

## 2. Research goals

The full snapshot enables questions that cannot be answered reliably from the Retraction Watch corpus alone:

1. How many OpenAlex works are currently marked `is_retracted=true`, and how does this compare with RW after identifier matching?
2. What is the publication-year distribution of retracted works?
3. When RW supplies a retraction date, how long is the publication-to-retraction lag?
4. What is the retraction **rate**, not merely the share of all retractions, by field, topic, country, institution, source, work type, OA status, and collaboration structure?
5. Are retractions concentrated among a small number of authors, institutions, journals/sources, publishers, countries, or topics?
6. Which retraction reasons in RW are associated with which OpenAlex topics/fields?
7. How much citation impact do retracted works accumulate, and how much occurs after the retraction event where a reliable retraction date is available?
8. How do the two datasets disagree: RW-only, OpenAlex-only, and matched works?

All results are descriptive unless a later analysis explicitly defines a causal/statistical inference design.

---

## 3. Data sources and roles

### 3.1 OpenAlex snapshot

Use the downloaded **Parquet** snapshot as the primary scholarly-graph and denominator source.

Required or expected entities:

- `works`
- `authors`
- `institutions`
- `sources`
- `publishers`
- `topics`
- `subfields`
- `fields`
- `domains`
- `countries`
- lookup entities required to interpret work type, OA, language, etc.

OpenAlex currently organizes its topic hierarchy as:

`Domain -> Field -> Subfield -> Topic`

Do not equate OpenAlex Topics with legacy Concepts or RW Subjects. They are separate classification systems and must remain separately labeled.

### 3.2 Retraction Watch

RW remains the stronger source for **retraction-event metadata**, especially:

- retraction date;
- publication date when present;
- retraction reason(s);
- notice nature/status;
- RW subject labels;
- journal/publisher strings in the RW record;
- author/affiliation strings as recorded by RW.

RW does not provide a complete denominator for all published works and therefore must not be used alone to compute field/country/institution retraction rates.

### 3.3 Joined dataset

A third analytical layer is produced only after matching:

`Retraction Watch <-> OpenAlex Work`

This joined layer supports analyses such as:

- Reason × OpenAlex Topic
- Reason × Field
- Retraction lag × Topic
- Retraction lag × Country
- post-retraction citation analysis
- RW/OpenAlex coverage comparison

The joined layer is not the same population as either source dataset and must be labeled accordingly.

---

## 4. Analysis populations

Every chart/table must declare which population it uses.

### Population A — OpenAlex retracted works

All unique OpenAlex works in the chosen snapshot satisfying the snapshot's retracted-work flag/definition.

Use for:

- OpenAlex retracted-work counts;
- publication-year trend;
- OpenAlex topic/field distributions;
- author/institution/country/source associations;
- citation characteristics;
- retraction-rate numerators when the denominator uses a compatible OpenAlex corpus.

### Population B — Retraction Watch retraction corpus

The deduplicated RW corpus defined by `docs/RESEARCH.md`.

Use for:

- retraction-event year;
- reason taxonomy;
- RW subject analysis;
- publication-to-retraction lag;
- notice/event-specific analyses.

### Population C — Matched RW × OpenAlex works

Only records linked with a documented matching rule and match status.

Use for cross-dataset analyses.

Never use Population C as if it represented all retracted papers unless measured coverage supports that claim.

### Population D — OpenAlex denominator corpus

All eligible OpenAlex works needed for rate calculations.

The denominator must match the numerator on:

- publication cohort;
- work type;
- field/topic attribution rule;
- country/institution attribution rule;
- snapshot/observation cutoff;
- any explicit inclusion/exclusion filters.

---

## 5. Core distinction: count, share, and rate

These must never be conflated.

### Retraction count

Number of retracted works associated with a group.

### Share of retractions

For group `g`:

`retracted works associated with g / all counted retraction associations`

This answers: **Where are observed retractions distributed?**

### Retraction rate

For group `g` and a defined publication cohort:

`retracted eligible works in g / all eligible works in g`

This answers: **What fraction of the group's eligible publication corpus is retracted by the observation cutoff?**

For comparability, publish rates per a convenient scale where useful, e.g. per 10,000 works.

Do not compute `retractions occurring in year t / papers published in year t` and label it a retraction rate. Retraction is delayed; cohort-based denominators or explicit survival/censoring methods are required.

---

## 6. Country attribution specification

### 6.1 Principle

A paper does **not** have a single intrinsic country. Country association is derived from:

`Work -> Authorship -> Institution -> Country`

Therefore the canonical stored representation should preserve all associated countries rather than overwrite them with one `paper_country`.

Recommended derived fields:

- `country_ids[]`
- `country_codes[]`
- `country_count`
- `first_author_country_ids[]` where available
- `corresponding_author_country_ids[]` where available/reliable
- `is_international_collaboration = country_count >= 2`

### 6.2 Default country analysis: full counting

For the primary country-affiliation distribution:

- deduplicate countries within each work;
- each work contributes at most `1` to each distinct associated country;
- multiple authors from the same country do not increase that country's count for that work;
- an international work may contribute `1` to multiple countries.

Example:

- Author A -> China
- Author B -> China
- Author C -> United States
- Author D -> Japan

Country full counts:

- China +1
- United States +1
- Japan +1

The sum across countries can exceed the number of unique papers.

### 6.3 Fractional country counting

Provide an optional fractional view:

`weight(country, work) = 1 / number of distinct known countries on the work`

A work linked to China, USA, and Japan contributes `1/3` to each.

Do not mix author-weighted fractional counting with country-equal fractional counting in the same metric. If author-weighted allocation is explored, publish it as a separate sensitivity analysis.

### 6.4 Country rate denominator

The numerator and denominator must use exactly the same attribution rule.

For full-count country rate:

`country-linked retracted works / country-linked eligible works`

with each work counted at most once per country in both numerator and denominator.

### 6.5 Labels

Prefer:

- `Country affiliation distribution`
- `Countries associated with retracted works`
- `Country-linked retraction rate`

Avoid ambiguous labels such as `Retractions by country` unless the methodology is shown immediately beside the chart.

---

## 7. Institution attribution

Use OpenAlex institution IDs for standardized institution analysis.

For each work:

- collect distinct institution IDs from authorships;
- deduplicate repeated affiliation of multiple authors to the same institution;
- preserve institution type and country where available;
- distinguish known institutions from unresolved/missing affiliation.

Primary metrics:

- retracted-work full count;
- fractional count;
- total eligible works;
- cohort retraction rate;
- median retraction lag where RW match exists;
- topic/field distribution;
- citation impact of retracted works;
- repeat-retraction author associations.

Do not interpret raw count as institutional quality or misconduct prevalence. Institution size, field mix, publication era, database coverage, and affiliation quality are confounders.

---

## 8. Author dimensions

OpenAlex author IDs allow analyses that RW raw names alone cannot support reliably.

Derived measures:

- unique retracted works per author;
- total eligible works per author;
- retraction share/rate where denominator quality is sufficient;
- first publication year;
- career age at publication/retraction;
- citation impact;
- coauthor network;
- number of institutions/countries associated with retracted works.

### Repeat-retraction authors

Recommended bands:

- 1
- 2
- 3–5
- 6–10
- >10 retracted works

Also calculate concentration measures:

- Top 1% share
- Top 5% share
- Top 10% share
- Gini coefficient
- optional HHI

The site must state that association with a retracted paper does not establish responsibility for the retraction.

---

## 9. Discipline and topic dimensions

Keep the following systems separate:

### RW Subject

Use only for RW-defined subject analyses.

### OpenAlex hierarchy

Use the current four-level OpenAlex topic hierarchy:

- Domain
- Field
- Subfield
- Topic

For each level support:

- retracted-work count;
- share of retractions;
- denominator work count;
- cohort retraction rate;
- annual trend;
- growth rate for sufficiently large baselines;
- retraction lag where matched to RW;
- reason composition where matched to RW;
- citation impact;
- country/institution composition.

### Primary vs multi-topic attribution

OpenAlex works can have a primary topic and multiple assigned topics. Publish two analytically distinct modes where useful:

1. **Primary-topic mode** — one primary classification path per work; useful for mutually interpretable totals.
2. **Any-topic mode** — a work contributes to every qualifying assigned topic; useful for topical association analysis.

Never merge these modes without labeling the counting rule.

### Concepts

If Concepts are retained from the snapshot for historical/lookup analysis, label them as legacy/separate vocabulary. Do not present Concept and Topic as equivalent levels in one hierarchy.

---

## 10. Time dimensions

### Publication time

At minimum:

- publication year;
- publication month where reliable;
- publication cohort.

### Retraction time

RW supplies the principal retraction-event date for the joined analysis.

OpenAlex `is_retracted` indicates status in the snapshot but should not be treated as a retraction-event date unless a documented date field/source supports it.

### Retraction lag

`lag_days = retraction_date - publication_date`

Publish:

- P25
- median
- P75
- P90
- distribution bands

Suggested bands:

- <1 year
- 1–2 years
- 2–5 years
- 5–10 years
- >10 years

Cross with:

- field/subfield/topic;
- reason;
- country;
- institution;
- source/publisher;
- work type.

Negative or impossible lags must be retained in a data-quality audit but excluded from valid-lag statistics.

---

## 11. Retraction reasons

Use RW reason labels as the event-level source.

Keep both:

- raw RW reason(s);
- a documented higher-level reason taxonomy for visualization.

Suggested high-level families (final mapping requires validation against the actual RW reason dictionary):

- Research integrity
- Publication/process integrity
- Research error/quality
- Ethics/compliance
- Authorship/conflict
- Legal/copyright
- Publisher/editorial/administrative
- Unknown/insufficient information

Reasons are multi-label. Never force a single reason unless a specific analysis explicitly defines a priority rule.

Key joined analyses:

- Reason × Field
- Reason × Subfield
- Reason × Topic
- Reason × Country
- Reason × Source/Publisher
- Reason × Retraction Lag
- Reason × Citation Impact

---

## 12. Source, journal, and publisher dimensions

Use OpenAlex source/publisher IDs where possible; retain RW journal/publisher strings for audit/comparison.

Metrics:

- retracted-work count;
- total eligible works;
- cohort retraction rate;
- annual retraction trend;
- median lag;
- reason composition;
- topic/field composition;
- citation distribution.

### Retraction bursts

Detect unusually concentrated retraction activity by source/publisher and time window.

A burst is a descriptive anomaly, not evidence of misconduct. Detection should require:

- minimum historical baseline;
- minimum event count;
- explicit algorithm/threshold;
- sensitivity to mass retraction/cleanup events.

Where RW records support it, annotate known bulk-retraction episodes separately from ordinary annual variation.

---

## 13. Work characteristics

Candidate OpenAlex dimensions:

- work type;
- language;
- open-access status;
- author count;
- institution count;
- country count;
- citation count;
- referenced-work count where useful;
- source type;
- publication venue;
- topic breadth.

Potential analyses:

- retraction rate by work type;
- retraction rate by OA status;
- team size vs retraction rate;
- domestic vs international collaboration;
- mono-institution vs multi-institution work;
- citation distribution of retracted vs eligible non-retracted works.

These are observational comparisons. Do not infer that OA, team size, international collaboration, or a specific publication model causes retraction without an appropriate design.

---

## 14. Collaboration dimensions

Derived fields per work:

- `author_count`
- `institution_count`
- `country_count`
- `is_multi_institution`
- `is_international`

Suggested collaboration classes:

- 1 country: domestic/single-country
- 2 countries: bilateral
- 3+ countries: multinational

Possible analyses:

- retraction rate by collaboration class;
- field-adjusted descriptive comparison;
- reason composition by collaboration class;
- retraction lag by collaboration class.

Network analyses may later include:

- author ↔ author
- institution ↔ institution
- country ↔ country

Only aggregate/network data suitable for publication should be exported to the website.

---

## 15. Citation impact and post-retraction citation analysis

### Static citation impact

For OpenAlex retracted works:

- citation count distribution;
- median/percentiles;
- highly cited retracted works;
- field-normalized citation measures where available and methodologically appropriate.

### Post-retraction citations

This analysis requires a reliable RW retraction date plus citation edges and citing-work publication dates.

For a matched retracted work:

- citations before retraction;
- citations after retraction;
- citations within 1/3/5 years after retraction;
- fraction of citations occurring after retraction.

Define:

`post_retraction_citation_ratio = post_retraction_citations / all dated citations`

Caveats:

- citation date is normally proxied by citing-work publication date;
- publication date granularity varies;
- a citation after retraction does not imply endorsement or ignorance of the retraction;
- citations may explicitly discuss the retraction.

This should be labeled **citation persistence after retraction**, not automatically “continued misinformation.”

---

## 16. Concentration analysis

Measure whether observed retractions are diffuse or concentrated across:

- authors;
- institutions;
- countries;
- sources/journals;
- publishers;
- fields/topics.

Recommended measures:

- top-k share;
- Top 1/5/10% share;
- Lorenz curve;
- Gini coefficient;
- optional HHI.

Always publish the relevant population and counting method beside the concentration statistic.

---

## 17. Cross-dataset coverage analysis

Create a reconciliation table with at least:

- RW unique works;
- RW works with DOI;
- RW DOI matched to OpenAlex;
- RW DOI unmatched;
- OpenAlex retracted works;
- OpenAlex retracted works matched to RW;
- OpenAlex retracted works not matched to RW;
- DOI conflicts/duplicates;
- merged/deleted OpenAlex ID cases.

Suggested match-status values:

- `exact_doi`
- `pmid_match`
- `other_exact_identifier`
- `ambiguous`
- `unmatched`
- `merged_or_redirected`
- `excluded_quality_issue`

Do not use title fuzzy matching in the primary high-confidence corpus unless separately specified, validated, and assigned a confidence tier.

### OpenAlex deletions / merges

The snapshot pipeline must account for the snapshot's current deletion/merge semantics. Do not assume that an old OpenAlex work ID remains independently valid forever. Preserve source OpenAlex IDs and log redirected/deleted/merged states during reconciliation.

---

## 18. Missing/unknown data

Missingness is an analytical result, not merely a cleaning nuisance.

For every major dimension publish coverage, for example:

- % with DOI;
- % matched to OpenAlex;
- % with at least one resolved institution;
- % with at least one resolved country;
- % with topic classification;
- % with valid publication date;
- % with valid retraction date;
- % with valid lag;
- % with usable citation dates.

Normalize placeholder strings only with explicit rules. Never merge genuine entities into `Unknown` because their names contain words such as “unknown” or “unavailable”.

---

## 19. Recommended first-release analysis set

The first snapshot-backed release should prioritize robust metrics rather than implementing every possible dimension.

### Tier 1 — foundation

1. OpenAlex retracted-work total and publication-year trend
2. RW vs OpenAlex coverage/reconciliation
3. Domain/Field/Subfield/Topic distribution
4. country-affiliation distribution using documented full counting
5. institution distribution using OpenAlex institution IDs
6. author distribution/repeat-retraction counts
7. source/publisher distribution
8. work type and OA status
9. denominator-backed cohort retraction rates for selected stable dimensions
10. complete data-quality/coverage report

### Tier 2 — joined analyses

1. RW Reason × OpenAlex Field/Topic
2. retraction lag × Field/Topic/Country
3. citation impact of retracted works
4. post-retraction citation persistence
5. author/institution/source concentration
6. domestic vs international collaboration
7. source/publisher retraction-burst detection

### Tier 3 — advanced research

1. survival/right-censoring analysis
2. matched controls or standardized comparisons
3. temporal topic-shift analysis
4. collaboration/retraction network analysis
5. multivariable models controlling publication year, field, work type, country, and source characteristics

---

## 20. Output artifacts

Raw OpenAlex snapshot files must **not** be committed to the GitHub repository or shipped with the React site.

Recommended local/intermediate outputs:

```text
data/local/openalex-snapshot/        # ignored; full snapshot
data/processed/openalex/             # ignored; intermediate tables
```

Recommended publishable outputs:

```text
public/data/openalex-summary.json
public/data/openalex-timeseries.json
public/data/openalex-fields.json
public/data/openalex-geography.json
public/data/openalex-institutions.json
public/data/openalex-authors.json
public/data/openalex-sources.json
public/data/openalex-coverage.json
public/data/rw-openalex-joined-summary.json
```

Exact filenames may be consolidated later, but front-end assets must contain only aggregated/statistically necessary data and a small audited sample where needed for explanation.

No raw Parquet, JSONL, Gzip snapshot partitions, or unrestricted paper-level exports should be committed for front-end deployment.

---

## 21. Pipeline architecture

Recommended stages:

```text
OpenAlex Parquet snapshot
        |
        v
[01 snapshot validation]
        |
        v
[02 canonical works extraction]
        |
        +----> denominator tables
        |
        v
[03 retracted works extraction]
        |
        +----> OpenAlex-only analysis
        |
Retraction Watch
        |
        v
[04 RW canonicalization]
        |
        v
[05 identifier reconciliation]
        |
        v
[06 joined analytical table]
        |
        +----> reason/topic/lag analyses
        +----> post-retraction citation analysis
        |
        v
[07 aggregation + QA]
        |
        v
[08 publish compact JSON]
        |
        v
React research site
```

DuckDB is a suitable default execution engine for Parquet exploration/aggregation because it can query snapshot partitions without importing the full dataset into a separate database. Production implementation may later use another engine if performance requires it.

---

## 22. Snapshot provenance

Every generated report must carry a manifest including at least:

```json
{
  "openalex_snapshot_date": null,
  "openalex_format": "parquet",
  "retraction_watch_snapshot_date": null,
  "generated_at": null,
  "pipeline_commit": null,
  "work_rows_scanned": null,
  "retracted_work_count": null,
  "rw_unique_work_count": null,
  "rw_oa_exact_match_count": null
}
```

Add checksums or source manifest identifiers where practical.

A result without snapshot provenance is not considered reproducible and should not be promoted to the public research site.

---

## 23. Validation gates before publication

The first full run must pass these checks:

- snapshot manifest/files are readable;
- no required entity directory is unexpectedly empty;
- unique OpenAlex work ID assumption is checked;
- `is_retracted` extraction count is reproducible;
- DOI normalization tests pass;
- matched DOI multiplicity is audited;
- country full-count sums are allowed to exceed paper count and are labeled correctly;
- fractional country weights sum to approximately one per work with known countries;
- rate numerator and denominator use identical group-attribution rules;
- publication/retraction negative lags are reported;
- unknown institution/country/topic shares are published;
- matched and unmatched RW/OA populations are reported;
- current-year/incomplete-cohort comparisons are not treated as complete historical rates;
- front-end build contains no raw snapshot files.

---

## 24. Front-end presentation principles

Every major visualization should expose:

1. **Question** — what is being investigated?
2. **Metric** — count, share, rate, lag, citation impact, etc.
3. **Population** — OA retracted, RW, joined, or OA denominator cohort.
4. **Counting rule** — unique, full count, fractional, primary-topic, any-topic, etc.
5. **Observation** — a generated factual statement from the plotted statistics.
6. **Interpretation limits** — what the chart does not establish.
7. **Data coverage** — missing/unknown/matched percentage when relevant.

Interactive toggles should not silently change statistical meaning. A switch between full and fractional counting, or count and rate, must update the chart title, axis label, tooltip, and methodology note together.

---

## 25. Non-goals / prohibited interpretations

This project must not present:

- raw retraction count as a ranking of research integrity;
- author association with a retracted paper as proof of misconduct;
- institution/country association as responsibility for the retraction;
- `share of global retractions` as `retraction rate`;
- an OpenAlex Topic as equivalent to an RW Subject;
- a limited matched sample as representative of all retractions without coverage evidence;
- post-retraction citation as proof that citing authors ignored the retraction;
- incomplete recent cohorts as directly comparable with mature historical cohorts;
- observational associations as causal effects.

---

## 26. Definition of done for this phase

The snapshot-backed analysis phase is considered complete when:

1. the full OpenAlex Parquet snapshot is validated and provenance is recorded;
2. OpenAlex retracted works are extracted reproducibly;
3. the denominator corpus is defined and tested;
4. RW ↔ OA reconciliation coverage is published;
5. country, institution, author, source, field/topic, work-type and OA-status dimensions are generated;
6. at least one valid denominator-backed retraction-rate analysis is published;
7. missingness/coverage statistics accompany the results;
8. aggregate JSON is generated for the React site without raw snapshot data;
9. methodology notes explain all counting/rate rules;
10. automated tests prevent regression in the key statistical definitions.

Only after these gates pass should more speculative/advanced analyses be promoted into the main Observatory navigation.
