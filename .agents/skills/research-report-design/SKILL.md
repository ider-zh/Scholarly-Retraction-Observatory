---
name: research-report-design
description: Design or redesign evidence-based research websites, data reports, and chart narratives. Use for website report layout, visual hierarchy, chart selection, report writing, and screenshot-based review, especially Scholarly Retraction Observatory. Not for marketing landing pages, changing statistical definitions, or generating unsupported research findings.
---

# Research Report Design

Build a readable research publication with an optional data explorer, not a query console dressed as a report.

## Precedence and working boundaries

- Follow the user's current brief, existing project constraints, statistical definitions, and published data contracts. These override generic aesthetic advice in other skills.
- Keep raw snapshots, credentials, private records, and large source archives out of the public site.
- Do not change the pipeline, denominators, published aggregate values, source inclusion rules, or methods to make a chart prettier. Request a separate analysis change when needed.
- Do not push, merge, deploy, delete existing reports, or install third-party hooks unless the user authorizes those actions.
- An installed skill is guidance, not evidence that a design or a statistic has passed review.
- Use at most one general visual-direction skill in a pass. Prefer Impeccable when present. Use other skills for distinct jobs, not competing design briefs.

## Read project context first

Read `AGENTS.md`, `package.json`, existing design documents, routing code, report components, and the published manifest. Distinguish planned capability from implemented and validated capability.

For Scholarly Retraction Observatory, start with:

- `docs/WEBSITE_REPORT_DESIGN.md`
- `docs/OPENALEX_SNAPSHOT_ANALYSIS_SPEC.md`
- `docs/RESEARCH.md`
- `src/report/SnapshotReport.jsx`
- `src/report/ReportGuide.jsx`
- `src/report/InteractiveChart.jsx`
- `src/report/reader.js`, `sources.js`, `schema.js`
- `src/report/snapshot.css`, `interaction.css`, and `entry.css`
- `public/data/snapshot/manifest.json` and the specific aggregate chunks needed for the requested page

Paths are inspection hints from a 2026-09-11 review. Resolve renamed files from the checkout; never treat old path names or the old 1,000-query audit as the current data coverage.

Do not infer that the deployed site equals the current Git branch. Record the reviewed commit, URL, release ID, and source dates separately.

## Load only the relevant reference

- Layout, typography, navigation: `references/layout-and-visual-system.md`
- Chart choice, encoding, integrity: `references/chart-selection-and-encoding.md`
- Headings, narrative, captions: `references/editorial-standard.md`
- Examples and what to borrow: `references/reference-cases.md`
- Browser checks and completion: `references/qa-acceptance.md`

## Workflow

### 1. Audit before editing

Capture the requested route at desktop and mobile sizes using a real browser. Inspect the first viewport and the full page; also inspect source code.

If browser access is unavailable, produce a **source-only audit**, identify the limitation, and do not claim to have seen live spacing, clipping, or contrast. A local checkout can be rendered separately; label it as local, not production.

Write a short audit with evidence, reader impact, and proposed correction. Look for redundant navigation, controls preceding findings, repeated disclaimers, card nesting, weak type hierarchy, and charts shrunk to fit navigation.

### 2. Identify the reader's job

Default audience: researchers, editors, journalists, and readers who want to understand findings before operating filters.

Write one sentence for the page's question. Identify one primary finding, its supporting chart, and the minimum scope statement needed to interpret it. If no defensible finding exists, use a research-question headline and show what is missing.

### 3. Separate reading from exploration

Provide an intentional reading route with a small, curated selection of published findings. Keep advanced slice selection in an explorer or a clearly secondary disclosure.

Do not add unrecognized query parameters casually. Preserve existing `#/snapshot/...` links, `sources`, `slice`, history, selected-source behavior, and error handling. A new view mode requires an explicit route contract and tests.

Use one site-level navigation and, only where needed, one contextual navigation. Do not simultaneously expose tabs, a full select menu, a second expanded sidebar, and previous/next pagination for the same decision.

### 4. Establish a design contract

Write or extend `DESIGN.md` with a compact token system and page anatomy. Choose layout and type based on actual Chinese and English content, not placeholder text.

Compare two low-cost wireframes; implement one. Do not build two complete applications to decide between them. The default direction for this project is a quiet, evidence-led research publication, not a marketing page or an operations dashboard.

### 5. Bind narrative to evidence

For every displayed claim, record the aggregate file, chart ID, slice ID, population, metric, observation cutoff, and relevant numerator/denominator. See the illustrative contract in `assets/report-section.template.json`; adapt it to the existing schema rather than replacing that schema.

A source/slice change must update the chart, title, observation, scope, sample size, export, and limitations together. Never keep a static claim after the selected evidence changes. Preserve numerator/denominator provenance in exports.

### 6. Build a vertical slice first

Implement the overview plus one representative analysis, using real published aggregate data. Prefer reusing current React components and supported chart primitives. Do not install another chart library or migrate to Next.js just for appearance.

Suggested component responsibilities, not required names:

`ReportHeader`, `ScopeSummary`, `FindingLead`, `Figure`, `FigureCaption`, `EvidenceNote`, `MethodDetails`, `ExplorerControls`.

Keep semantic text and critical chart interpretation outside tooltips. All interactive figures need a keyboard/touch path and an accessible table or equivalent data representation.

### 7. Verify in bounded passes

Run project checks, compare aggregate outputs, and perform browser QA. Inspect desktop, tablet, and mobile in one batch; fix the observed defects in one batch; confirm with one further batch. Record unresolved defects rather than polishing indefinitely.

Use Impeccable for visual critique/polish when available, Vercel web-design-guidelines for interface review, and a browser skill for actual rendering. None replaces the data or editorial review.

### 8. Deliver evidence, not adjectives

Report exactly what changed, which commands ran, which routes/states were checked, screenshot paths, preserved data contracts, and remaining limitations. Do not call a page production-ready based solely on a successful build or a self-assigned design score.

## Non-negotiable research integrity

- Joint RW/OA analysis is not automatically a deduplicated union. Do not sum source totals without an explicit union contract.
- Match, cross-check, and independent validation are different claims. Do not describe dependent sources as independent evidence.
- Keep records, distinct papers, notices, authors, institutions, and relationships as separate units.
- Distinguish publication year from retraction/event year, and both from snapshot/observation date.
- Counts, within-retracted-sample shares, and retraction proportions among all publications are different metrics.
- A rate/proportion requires a compatible numerator and denominator, including scope and observation opportunity.
- Missing, not computed, not applicable, not published, and observed zero are distinct states.
- Topics and Concepts retain their own hierarchy and coverage; do not merge them into one taxonomy.
- Country/author/institution association is not nationality or misconduct responsibility.
- Preserve the project's normalization of missing affiliations; do not turn Unknown/unavailable into several competing institutions.
- Distinguish interquartile ranges from confidence intervals, and temporal association from causal explanation.

## Definition of done

The page communicates a question and evidence before asking the reader to operate a control. Critical scope remains visible, long methods are discoverable, supported deep links work, and actual rendered screenshots have been inspected. Without browser inspection, explicitly mark visual acceptance as pending.
