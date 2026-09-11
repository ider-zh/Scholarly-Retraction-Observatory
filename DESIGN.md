# Snapshot overview: reading before exploration

First-round scope: overview and the published `screening/A0-screening` figure only. Other chapters keep their existing layout. The user must accept this slice before any chapter-wide rollout.

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

Scoped to `.report-overview`, never global overrides of other chapters:

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
