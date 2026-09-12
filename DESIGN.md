# Snapshot overview: reading before exploration

## Report index and v2 presentation

The proportion extension retains the approved count pages and adds three adjacent evidence pages (15 slides total): within-Concept proportion for the same six count-leading subjects, common-scale within-Concept annual proportions for the same three subjects, and a within-country proportion map. It reuses the report's proportion helpers and compatible publication denominators. Small-base years break trend connections, null denominators remain unavailable, and small-base countries use a pattern rather than a value color. A fixed comparison set is not labeled the global proportion Top 6. Percentages use sufficient decimal precision to distinguish small values; n/N is visible on the comparison figure and available for every trend year in the accessible table.

The website's all-Concept annual comparisons also share the existing count/proportion route metric. One nearby control updates both root and child comparisons; percentage legends expose same-year n/N, and axes use eligible data rather than count-scale minima. Small-base points remain in tables/exports but are not drawn or bridged. See `docs/CONCEPT_COMPARISON_REVIEW.md`.

The follow-up presentation is 12 slides: cover, three front-loaded research-synthesis pages, source paths, screening, annual records, a three-taxonomy summary, Concepts top-six distribution, three shared-scale Concepts yearly plots, an offline country map, and an expanded citation explanation. Generic closing and author-disambiguation slides are removed; author interpretation remains in the full report. The three summaries introduce scope, geographic/disciplinary distribution and post-retraction citation without claiming an external literature review.

The updated index places a timezone-explicit build stamp immediately below each title. v1/v2 dates are the recorded report-data build timestamps; PPT uses its actual generated HTML timestamp. Source cutoff dates remain separate. Dates are generated from metadata, never fabricated from file modification time.

Compared a single overlaid three-series trend against small multiples; selected shared-axis small multiples to keep concept labels direct and avoid overlap. Reuse existing exact-code Natural Earth geometry and existing linear map color rules. Citation design separates target-paper coverage from mean/median cumulative citation counts. Retain academic-paper/report typography and ink/teal tokens, adding only neutral missing/unobserved swatches. No marketing-style cards or decorative effects.

The root URL is a publication index with exactly three primary entries: `#/report-v1`, the unchanged `#/snapshot/overview?sources=rw%2Coa`, and `presentation-v2/index.html`. Report v1 retains its original dataset and internal tabs. Snapshot source/slice routes are unchanged. The v2 sidebar links explicitly to v1 and the index.

Two low-cost index structures were considered: three equal dashboard cards, or a vertical publication list (`identity / reading intent / three title–description–link rows / scope note`). The list is selected: versions are reading choices, not comparable metrics. Left alignment, ample whitespace, Chinese serif heading and system sans body; ink `#172f46`, muted `#526579`, rule `#d5dfe6`, accent `#176b78`, no hero metrics or decorative gradients.

The 10-slide HTML-PPT adapts the html-ppt skill's starter and existing layouts with the `academic-paper` theme. It reuses the report's restrained ink/teal tokens and local CJK system fonts. Static bars and an annual column plot retain visible units, dates, source labels, limitations, accessible tables, exports and evidence links. A responsive reading layout replaces tiny scaled 16:9 content on phones; only the current slide is keyboard-accessible. Statistics are read from validated published chunks by `scripts/build-presentation.mjs`, never recomputed from raw sources. This is a curated v2 summary, not all report slices.

The subsequent lag and taxonomy revision is in `docs/LAG_TAXONOMY_REVIEW.md`: T4 leads with published quantile times rather than a full-width long-tail ECDF; RW Subject, OA Topics and OA Concepts each have a top-level chapter. Legacy `fields` links remain supported but are no longer a mixed entry in the main directory.

The latest reading/interaction revision is documented in `docs/READING_INTERACTION_REVIEW.md`. It supersedes the collapsed explorer and new-tab-only card behavior below: directories open by default immediately before continue-reading; ordinary card activation opens an isolated native dialog. Chapter figures, dialogs and standalone topics reuse `TopicAnalysis`. Default OA discipline navigation uses legacy Concepts; explicit taxonomy and slice links retain their requested analysis. No statistical contracts change.

The subsequent data-topic routing/index contract is in `docs/DATA_TOPIC_ROUTING.md`: chapter content stays in place, source-filtered cards open independent topics, and related published slices share explicit dataset/method controls.

The latest navigation revision replaces the horizontal chapter directory with a persistent desktop sidebar and a compact-screen drawer. Topic breadcrumbs remain in the content area; see `docs/SIDEBAR_NAVIGATION_REVIEW.md`. This supersedes the earlier top-directory layout, not its data or routing contracts.

First-round scope was overview and the published `screening/A0-screening` figure. The user has now accepted the sample and requested the second-round chapter rollout; its contract is recorded below.

## Baseline and alternatives

Reviewed checkout: `d035224b86a8e4716afdbceea858b52bc9918eea`; local URL `http://127.0.0.1:4173/#/snapshot/overview?sources=rw%2Coa`. The deployed route also rendered; its screenshot is a separate baseline, not proof of its Git revision. Published local release: `oa-2026-06-26-0d8f97ed1bf5`; OA 2026-06-26, RW 2026-09-10.

The desktop screenshot shows controls and definitions before evidence, with two sidebars, shortcut buttons, a select and pagination. The mobile first viewport contains almost exclusively source selection. The original local full-page heights were 2,812 / 3,009 / 4,355 px at the three requested widths.

Two low-cost wireframes considered:

```text
A — editorial column (chosen)        B — chapter rail + editorial column
Identity / collapsed chapter menu   Identity
Question and source/date scope      Chapter rail | Question and scope
Evidence-led finding                             | Finding
Full-width figure                                | Figure
Caption, interpretation, methods                 | Caption and methods
Collapsed source/slice explorer                  | Explorer
Continue reading
```

A gives the figure more space and avoids carrying a rail into tablet/mobile. One compact chapter disclosure retains all chapter links. A secondary source/slice disclosure replaces competing analysis controls; no new URL parameter is introduced.

## Tokens and anatomy

Originally scoped to `.report-overview`; the accepted tokens are now shared through `.report-publication`, never global overrides of the legacy RW site:

- Surface `#fffefb`, ink `#20313d`, secondary ink `#52616c`, rule `#d9dedf`.
- OA accent `#176b73`, neutral excluded marks `#77838b`; labels, not color alone, identify retained/excluded records. No misconduct color coding.
- Maximum content width 1,120 px; prose up to 44 em; body 17 px / 1.8; mobile 16 px. Chinese system stack, no remote font dependency.
- Title 36 px desktop / 28 px mobile; figure title 24 / 21 px; captions 13 px. Spacing 8, 16, 24, 40, 56 px.
- Page sequence: question → concise scope → supported finding → dominant figure → visible boundary → table/export and detailed methods → advanced exploration → next chapters.

## Evidence and routing contract

The overview defaults to the existing screening slice where OA is selected. Explicit `slice` links still resolve exactly, including population accounting and work types. Source filtering remains `filterCharts` / `sourceProfile`; no direct B count is extracted from the cross-source chart for RW-only use. RW-only currently has no overview slice, so it receives an explicit unavailable state and links to its published time/discipline chapters, not a fabricated figure.

Narrative and figure bindings include aggregate path, release, chart/slice IDs, population, metric, cutoff and evidence cell n/N/value. No pipeline or public aggregate file changes. The lead uses the published retained count and share, not a new estimate. The chart uses each published percentage and count as-is; formatting does not modify exported precision. Bar baseline 0, axis 0–100%; categories are mutually exclusive, not a funnel. A zero bar has no artificial minimum width. Null remains unavailable, never zero.

All five screening groups remain visible, with direct labels, keyboard/touch selection, caption, original n/N table, existing CSV exporter, and full method/quality/technical disclosures. Counts of records and papers remain distinct. Source dates are separate. Joint selection never means a union; OA flags and identity screening are not independent of RW.

## References

Borrow reading structure, not brand or code: [OWID Data Insights](https://ourworldindata.org/latest?type=data-insight), [Stanford AI Index 2025](https://hai.stanford.edu/ai-index/2025-ai-index-report), and [FT Visual Vocabulary](https://ft-interactive.github.io/visual-vocabulary/). These references are not evidence for the observatory's findings.

The supplied `research-report-design` skill is installed under `.agents/skills`. Impeccable, web-design-guidelines and Playwright skills were not found. Browser validation uses the already installed Playwright library and Chromium; no extra hooks, dependencies or font packages are installed.

## Second-round chapter rollout

Baseline checkout: `2630447267d4c8daf3311880008863b4fe02ee38`. Local screenshots of the eight remaining chapters showed exploration controls before evidence. The same two wireframes above apply: retain the accepted editorial column, not a new permanent chapter rail. The fields chapter keeps a contextual tree inside a disclosure; it is a navigation tool, not an expanded prerequisite for reading.

Shared `ReportHeader` / `ReportScope` keep the publication identity, one chapter menu and visible dataset dates. `ChapterReport` follows question → concise scope → evidence-bound observation → figure → boundaries and detailed methods → advanced analysis selector. All 106 non-overview slices remain available. The source/slice explorer resets to collapsed on chapter changes, but stays open during source switching. Sources remain checkboxes because a joint selection is an analysis collection, not a new union population.

`Figure` and `FigureCaption` provide the shared figure grammar. `ResearchFigure` binds the first published observation, scope, units, date, complete table, original CSV and evidence identifiers to the same active chart. It does not introduce a new computation or select a different plot grammar: lines retain time/order, matrices retain paired dimensions, scatter retains joint distributions, intervals retain their original uncertainty semantics, and control charts retain their published policy. Detailed supplementary values and audits remain discoverable.

The fields explorer retains Subjects, Topics and historical Concepts as separate systems, including every main/subdiscipline node, multi-parent navigation, missing groups, metric restrictions, distribution/time pairing, full exports and deep links. Its node totals precede the figures; full methods follow them. Critical Concepts historical-parent and matched-population cutoff boundaries remain visible. Figure-local Top N selection never changes denominators or trims the full tree or exports.

No changes to public aggregates, manifest, pipeline, schema, source classification, taxonomy computations or hash parameter parsing. Local browser QA covers all 106 exact slice exports, the eight chapter source-selection sets, three viewport sizes, discipline navigation/metrics and an overview regression. See `docs/CHAPTER_REDESIGN_REVIEW.md` for actual evidence and remaining limitations.

## Follow-up: persistent directory and LAN access

The user's subsequent request overrides the collapsed chapter menu: all ten existing links now remain visible in a sticky masthead, with the current chapter underlined. Desktop uses a wrapping horizontal row; mobile uses three columns, not another hidden menu. Advanced source/slice exploration remains secondary. Scroll margins leave room for the masthead when opening analyses or focusing chart points.

The always-visible mobile directory uses more vertical space: the finding may continue below the first viewport. The mobile regression now checks all directory links are initially visible and the finding precedes the plot, rather than enforcing the previous collapsed-menu fold budget.

LAN HTTP now retains byte-length and SHA-256 checks using a bundled `@noble/hashes` fallback when Web Crypto is absent. This does not authenticate HTTP transport or its manifest. No statistical data or expected checksums change. Native and fallback tests cover all published files, a standard vector and corruption rejection; actual LAN Chromium checks cover 1440×900, 768×1024 and 390×844, sticky navigation after scrolling, chapter links, axe and a same-length tampered response. Before/after screenshots and results are in `/tmp/sro-lan-review/`; desktop and mobile were visually inspected. No push or deployment is performed.

## Follow-up: one range control

`ChartRange` uses the existing-library approach requested by the user: pinned `rc-slider` 11.1.9, one track with two handles and a single visible start–end label. See the [component documentation](https://github.com/react-component/slider). It replaces both native range inputs in line/control charts without changing `rows.slice(start, end + 1)`, row values or exports. Handles cannot cross but may coincide to display one point. The index-based selection also works with months, citation counts and other non-year labels; screen readers receive the original label, not the index. Keyboard operation and reset remain available. Local before/after screenshots and browser evidence: `/tmp/sro-range-review/`; reproducible checks: `scripts/check-chart-range-browser.mjs`.

## Country map and consolidated country topic

The user requested removal of the article/journal explanatory disclosure and consolidation of the two country-rate topics. The disclosure is removed, not the article scope or screening rules. Tests verify the old rate slices and country explorer have identical n/N, dates and attribution; the legacy rate values differ only by published rounding. Hide the redundant topic from the catalog when the explorer exists, retaining old links and precise exports with a link to the replacement. Legacy eligible rate bars are sorted by their value rather than count; small bases remain outside ranking.

Two low-cost options were considered: a permanently stacked map and bar chart, or one shared figure with map/bar controls. The latter is selected to avoid repeating the same evidence and making the chapter longer. The existing research typography and figure caption remain; the map is the only new dominant visual, not another dashboard card. Its palette is a zero swatch `#e1f0ed`, sequential values `#aed4cd`, `#68aaa1`, `#28776f`, `#124e48`, and missing gray `#e3e5e7`. Small bases use a pattern, not an apparently low value. The existing chapter navigation remains unchanged.

`CountryMap` uses offline preprojected Natural Earth paths and exact country-code joins. Selection updates the existing node and annual graph; metric/population updates change map values and legends together. A linear scale uses the full eligible country set, never the bar search/Top N subset. Missing, undefined, low-base and measured-zero states remain distinct. All countries, including those absent from the simplified geometry, remain available in the selector and CSV. No new research metric, denominator, union or statistical release is computed. See `docs/COUNTRY_MAP_REVIEW.md` and `src/report/assets/README.md`.

## Follow-up: within-discipline and country proportions

The explicit analysis extension adds `proportion` (%) alongside existing count, sample share and per-10k metrics. Shared native `MetricChoices` radios stay visible with the figures; Topics and Concepts retain their separate two-level trees. Percentage plots start at zero and use the actual positive maximum, not a forced 1% ceiling. Country selectors wrap within the editorial column, including modal and mobile layouts. No charting-stack migration is needed.

Country publication-year cohorts are an additive, provenance-validated aggregate, not a cosmetic recomputation. Same-node/same-country annual publication denominators, OA observation cutoff, matched-subset restrictions, missingness and non-additivity remain explicit. Country cards open the existing independent topic dialog; old slice links and CSV contracts remain. See `docs/COHORT_PROPORTION_REVIEW.md` for scope, reproducibility, local aggregate version and actual checks.

## Follow-up: full Topics hierarchy

Topics now starts with the four Domain categories, then Field, Subfield and actual Topic leaves. Prefer a progressive native disclosure tree over an initially expanded thousands-node directory. Search spans all levels, breadcrumbs retain the full path, and selecting any level updates its distribution and publication-cohort series. Subject and Concepts retain their own two-level navigation. Reuse the existing figure grammar and tokens; do not add another competing page directory.

Four-level counts and compatible annual denominators are newly scanned and validated, not inferred from labels or borrowed from parent nodes. Lossless, bounded zlib decoding keeps the complete catalog within the existing aggregate payload budget. See `docs/TOPIC_HIERARCHY_REVIEW.md` for data/encoding contracts, source provenance, local screenshots and actual validation.

## Follow-up: separate author-name and identity rankings

Compare two lightweight options: one combined ranking with a dataset switch, or two explicitly named topic entries. Use separate entries because RW raw strings and OpenAlex author IDs are different aggregation keys, not interchangeable measurements of the same people. Keep the existing research typography, colors, figure captions and accessible tables; no new visual tokens or chart library. In the OA topic, retain the existing single-choice OA-flagged / RW-matched populations and their old deep links. RW gets its own source-scoped table, with missing placeholders outside the ranking and the full original-paper scope visible. See `docs/AUTHOR_RANKING_REVIEW.md`.
