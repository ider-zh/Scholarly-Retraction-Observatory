# Original-first broad Work policy

## Owner decision

The owner approved removing automatic exclusions based on title prefixes,
OpenAlex type and conflicting identifier evidence. Policy version:
`original-first-independent-notices-v2`.

The new analysis retains core Works of **all types** as candidates, subject to
the same publication-date cutoff. This includes reviews and records whose type
alone previously caused exclusion. It is not a claim that every retained Work is
a verified research article. Publication denominators use the same broad rule.

An independent notice is excluded only when an RW notice identifier links to a
different, comparable original DOI/PMID and the Work does not itself match RW
original identifiers. Same-identifier links, missing comparable identifiers,
type labels and title prefixes do not establish this relationship. Conflicting
original/notice evidence is retained with an uncertainty flag. Matching ambiguity
between multiple distinct Works is still not resolved by arbitrary selection.

## Isolated recomputation

`pipeline.broad_snapshot` creates a new content-addressed run outside the original
run directory. It changes only derived role classifications and conservatively
rebuilds cohort counts from the validated original scan; immutable target metadata
is reused through hard links. It does not rewrite the source snapshot or old run.
Per-shard and global counts are conserved. Parent configuration, derivation code
and policy hashes remain in provenance.

The report and downstream scans detect the explicit broad-policy configuration;
legacy runs retain their existing interpretation. Dimension, taxonomy, Concepts,
incoming-citation and supplementary scans must be recomputed for the new run.
Prior marker configuration hashes cannot be substituted. No broad numerator is
divided by a legacy article-only denominator. Existing article/review-specific
annual slices remain labeled as narrower comparisons; a separate all-type slice
is added for the broad cohort.

The previous 10 sampled cases are reassessed rather than replaced with hand-picked
cases. Their old grouping and exclusion explanation remain visible as historical
context beside their current decision and distinct-original evidence. Sampling
does not estimate misclassification prevalence.

## Evidence and limitations

The user-identified Springer example `10.1007/s11277-021-08713-8` is a retracted
original, illustrating why title prefixes are insufficient. Conversely,
`10.1038/nature11164` is a separate Nature retraction note pointing to original
`10.1038/nature08456`. Not every retraction-titled record is an original renamed.

This rule favors recall over specificity. Unresolved notices may remain among
candidates when no usable identifier relationship is present. Counts therefore
describe broad database candidates, not independently confirmed original papers.
RW dependence, institution-country attribution, snapshot cutoffs, missingness and
unequal observation windows remain unchanged.

## Recomputed scope

The immutable parent run is `0a8226b31ea961c53cfbf4525b0cb89ffe187d26a3225d651341b03ceedb80a1`.
The isolated broad run is `c05efc0d85c4b20e357f558120235726d6faf69ebe397e6999901c92f720ca87`
under `/mnt/hg02/openalex-snapshot/analysis/broad-runs/`.

| Measure | Historical article policy | Broad policy |
| --- | ---: | ---: |
| Core flagged Works, A0 | 114,538 | 114,538 |
| Eligible flagged candidates, A1 | 50,331 | 81,034 |
| Uniquely matched OA Works, C | 46,283 | 60,311 |
| Same-policy publication denominator, D | 216,416,450 | 315,052,767 |

Broad screening partitions A0 into 81,034 retained candidates (70.748573%),
33,359 independently linked notices and 145 date-ineligible records. These are
screening proportions, not population retraction rates. D includes all eligible
publication years; charts starting in 2000 use their own corresponding subtotal.
Of the retained candidates, 57,398 retain a review flag (unresolved identity,
notice/title evidence or a non-article source type); this is not an estimate of
misclassification. C increases because original/notice role conflicts no longer
automatically reject an otherwise unique identifier match. DOI/PMID disagreement
and multiple-Work identifier ambiguity still block selection.

The unchanged ten examples now comprise six retained candidates and four
excluded notices. Their Work IDs and old strata are retained in the public
reassessment sidecar; the four notices expose the distinct original identifier.
No record was selected to replace an inconvenient earlier example.

All five extension scans cover all 2,446 manifest-listed Work shards. Dimensions
and taxonomy ran concurrently at 4 workers × 6 threads each; citations and
Concepts used the same concurrency. Supplement used 6 workers × 8 threads.
Each worker had a 32 GB DuckDB memory ceiling. No old denominator marker was
copied into the new run. Full source files and the original analysis run remain
unchanged.

The initial report attempt was deliberately staged before extensions completed
to materialize RW matching for the incoming-citation scan. It failed the publisher
denominator check and was not published. Final generation waits for all scans;
publication must pass the complete report's reconciliation and public-data gates.
The first complete staged report was also blocked by duplicate annual IDs in
fixed-publication followup slices: multiple eligible document types needed to be
summed by year before calculating the rate. The builder now does that, with an
end-to-end synthetic retraction/review/notice regression test. No invalid report
was installed into the local public assets.

## Local acceptance

- Release: `oa-2026-06-26-e5c7695e3e2a`, generated
  `2026-09-12T10:48:18.766035+00:00`; 112 chart slices.
- Reviewed checkout HEAD: `767ed56643ce1d271120788b96f0744918788216`, with
  pre-existing local changes preserved. No commit, push or deployment.
- Browser: local `http://127.0.0.1:5186/`, Chromium `136.0.7103.25`.
- `python -m unittest discover -s tests`: 70 passed, including a synthetic complete
  broad-policy pipeline with retraction/review/notice types and fixed-window sums.
- `node --test tests/*.test.mjs`: 85 passed. Baseline assertions now follow the
  declared slice inventory and same-release values instead of historical totals.
- `npm run build`: passed, including HTML-PPT regeneration and public/dist data
  validation. The existing large-JavaScript-chunk warning remains.
- Public statistics payload: 2,096,986 bytes, below the unchanged 2 MiB limit but
  with only 166 bytes of headroom. No data was truncated to fit. The sample sidecar
  omits redundant current-role/uncertainty fields (derivable from its evidence and
  outcome), and duplicate historical aggregate counts; parent provenance, old
  strata, all ten original records and current decisions remain available.
- `check-screening-examples-browser.mjs`: six groups passed at 1440×900,
  768×1024 and 390×844. RW/OA/joint choices, old screening/work-type links, keyboard
  pinning, aggregate CSV, sample JSON and rejection of a tampered sample all passed.
  The first harness attempt retained scroll/disclosure state when revisiting the
  identical hash; explicit reload fixed the harness and the confirming run passed.
- `check-cohort-browser.mjs`: nine groups passed. Topics/Concepts parent and child
  nodes, four metrics, A1/C_D selection, annual CSV n/N, country switching,
  source restrictions, modal/deep-link behavior and three-size WCAG checks passed.
- `check-country-merge-browser.mjs`: 12 website/PPT map states passed; existing
  country grouping, exported counts and shared-color behavior remain consistent.

Screenshots inspected: `/tmp/sro-broad-review/confirm/desktop-overview.png`,
`tablet-overview.png`, `mobile-overview.png`, `mobile-uncertain.png`, plus
`/tmp/sro-broad-review/cohorts/desktop-concepts-time.png` and
`desktop-geography-distribution.png`. Before-policy evidence remains in
`/tmp/sro-screening-examples/confirm/`. Full browser check records and additional
screenshots are under `/tmp/sro-broad-review/{confirm,cohorts,maps}/`.

Primary implementation files: `pipeline/work_policy.py`, `pipeline/broad_snapshot.py`,
the five snapshot extension scanners, `pipeline/snapshot_report.py` and its
country/publisher/taxonomy/supplement/citation adapters. Reader changes bind the
policy to scope text, population labels, methods, the screening figure and the
reassessment examples. Source/slice contracts, accessible tables, hashes and
exports remain enforced. No uncertainty is relabeled as confirmed original-paper
identity, and RW and OA are not added together.
