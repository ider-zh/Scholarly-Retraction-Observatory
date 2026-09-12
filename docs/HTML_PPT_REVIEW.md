# Report index and HTML-PPT (v2)

## Proportion extension (current: 15 slides)

The approved 12-slide presentation is retained with three inserted proportion pages:

- Slide 11: within-Concept retraction proportions among the **same six count-leading subjects**, sorted by proportion, with visible `n / N`. This is not a global proportion Top 6.
- Slide 12: Medicine, Biology and Computer science proportions by original publication year, using a shared percentage axis. Each year uses that subject's same-year full eligible publication denominator.
- Slide 14: within-country proportion map for 2000–2026 publication cohorts, with eligible-country Top 3, exact n/N and explicit small-base/missing states. The original all-period count map is slide 13; their scopes and scales are distinct. Citation explanation moves to slide 15.

Formula is `screened flagged papers associated with subject/country / all eligible publications in the same subject/country and scope × 100%`. It is not share of the retracted sample. RW Subject has no compatible all-publication denominator, so no RW retraction proportion is invented. Data/source cutoffs and build timestamp remain separate.

`disciplineEvidence` now accepts a metric and reuses existing `resolveStudy`, `distributionRows` and `disciplineTimeChart`; country evidence reuses `countryStudy`. No source aggregation or pipeline reruns occur. All 16 evidence contracts retain full published rows or exact existing frontend projections. Percentage rows keep full precision in tables/exports (subject comparison displays four decimals).

For proportions, `n ≥ 20` and `N ≥ 1,000` are required for ranking, map color and trend connections. Small-base annual values remain in tables; baseline crosses are explicitly non-quantitative missing-reliability markers, not zero. Null denominators break lines and are not converted to zero. Last-year eligible segments are dashed. Neither denominator adjustment nor historical trends remove unequal observation windows or establish causal risk.

Additional files: `scripts/presentation-country-proportion.mjs` and its focused tests. Updated generator/helpers, presentation CSS/evidence table labeling, contract/browser tests and README. The frontend stack and original published data remain unchanged. Work split between root (subject figures/integration), country-proportion helper agent, and QA agent at the user's request.

Before screenshots: `/tmp/sro-ppt-proportion-before/slide-{9,10}.png`. Browser review: `/tmp/sro-ppt-proportions-review/`; final confirmation: `/tmp/sro-ppt-proportions-confirm/`. Local browser checks use `http://127.0.0.1:5186/` after the prior dev server stopped. No deployment, commit or push requested or performed.

Validation: `npm run build` passed; `node --test tests/presentation*.test.mjs tests/publication-builds.test.mjs tests/snapshot-*.test.mjs` passed all 76 tests; `sha256sum -c /tmp/sro-proportion-contracts.sha256` and `git diff --check` passed. Public-data guard reports 2,016,328 bytes and 36 samples, within its 2 MiB budget. The existing large-bundle warning remains. Browser QA covers all slides at 1440×900, 768×1024 and 390×844, proportion exports/deep links, map semantics and keyboard-accessible tables. Visual review caught a clipped country heading and footer overlap; compact country ranking, safe centering and in-flow footers address the layout causes. Browser assertions now verify heading visibility and final content/footer reachability, not merely horizontal overflow. Older iteration records below describe their historical scope, not the current slide count.

Final proportion confirmation: all six browser groups and 45 slide/device layout checks passed with no page errors. Desktop and mobile country-map top/bottom screenshots were visually inspected. The desktop country proportion slide still requires about 110 px of vertical scrolling for its final limitations/footer; these remain reachable and no longer overlap. No physical-device or deployed-site review was performed.

## Current revision: synthesis, research figures and build dates

2026-09-12 follow-up, local-only. The earlier ten-slide delivery recorded below is superseded by a **12-slide deck**:

1. Cover.
2. Research synthesis: the question and source populations.
3. Research synthesis: discipline/geographic distribution and why quantity is not risk.
4. Research synthesis: post-retraction citation coverage and mean versus median.
5. Separate RW / OA source paths.
6. Screening of flagged records.
7. RW annual first-recorded retractions.
8. RW Subject, OpenAlex Topic and Concepts summaries, each with its own population and data table.
9. Concepts level-0 top-six distribution; full 19 categories retained in the table/export.
10. Medicine, Biology and Computer science by original publication year, sharing one count axis; 2026 partial-year segment dashed.
11. Offline country map replacing the collaboration-completeness slide.
12. Citation coverage and cumulative 1/3/5-year windows replacing the ambiguous five-year mean-only slide.

Removed standalone author-disambiguation and generic closing slides. The original report's author explanation is unchanged. All three front pages synthesize this report's evidence, not an external literature review.

### Evidence changes

- `scripts/presentation-figures.mjs` reuses `resolveStudy`, `distributionRows`, `disciplineTimeChart` and map scale/color helpers. The taxonomy summaries and three trend series are exact projections of the validated, already-published `fields.json` explorer. No statistical pipeline or public aggregate files change.
- Topic summary uses the same complete primary-topic tree aggregates as the website explorer. It does not silently mix these with the older separate F1 main-domain chart. RW Subject and Concepts multi-label counts are not additive.
- Map: decoded `G1/A1-institution_country` from `geography.json`, 177 local Natural Earth paths, exact code joins, linear count scale. Observed zero and missing are distinct. All 178 published country rows remain in the table/export; 26 have no matching geometry. No tiles, API, territorial aliasing or geographic inference.
- Citation evidence: unchanged `C4/C-incoming-common_5y`. The narrative separates 10,081 / 12,923 targets with at least one observed citation (78.01%) from cumulative mean citation counts 2.88 / 6.49 / 9.01 and medians 1 / 2 / 3. The same eligible cohort is used in all windows. Zero observation is qualified, and 29,938 excluded targets are disclosed. Additional table columns expose coverage, median and exclusions.
- Eleven embedded evidence contracts retain full rows and metadata. Displayed subsets, source dates and denominators remain explicit; ordinary chart evidence is byte-contract-equivalent after standard decoding.

### Homepage dates

Each entry shows a prominent timestamp directly below its title, in UTC+8, separately from data cutoffs. Report v1 uses `report.json.meta.generated_at`; Report v2 uses `manifest.generated_at`; HTML-PPT uses the actual build timestamp also written to its HTML `build-date` meta tag. `scripts/publication-builds.mjs` writes `src/publication-builds.js` during deck generation. The two reports are labeled **报告数据构建时间**, not falsely described as newly rebuilt datasets.

### Verification and evidence

Local dev review URL: `http://127.0.0.1:5184/`. Statistical release remains `oa-2026-06-26-1f41fe8f2476`.

- `npm run build`: passed, including timestamp generation and public-data guard; aggregate payload remains 2,016,328 bytes / 36 samples. Existing large-bundle warning remains.
- `node --test tests/presentation.test.mjs tests/publication-builds.test.mjs tests/snapshot-*.test.mjs`: 69 passed (presentation contracts, dates, HTML/index timestamp equality, routes, map missing/zero, shared-axis trends and citations plus existing report tests).
- `sha256sum -c /tmp/sro-ppt-revision-contracts.sha256`: all initial `public/data` and `pipeline` bytes unchanged. `git diff --check`: passed.
- Browser audit and confirmation use Chromium, Playwright and axe at 1440×900, 768×1024 and 390×844. All pages have keyboard-accessible evidence dialogs/exports. Date stamps, report routes, source filters, all evidence links and presenter popup are checked. Long mobile slides also have bottom-of-slide captures.
- Before: `/tmp/sro-ppt-r2-before/slide-{5..10}.png`; homepage baseline `/tmp/sro-index-dates/before.png`.
- Initial revision: `/tmp/sro-ppt-revision-review/`, including all slide/viewport screenshots. Root reviewed the three overview slides, trend, map, citation page and index. The initial targeted citation assertion was updated to match the actual visible wording; no numerical correction was needed.
- Index screenshots: `/tmp/sro-index-dates/after-{desktop,tablet,mobile}.png`.
- Final browser confirmation: `/tmp/sro-ppt-revision-confirm/`, with machine-readable `checks.json` and per-slide screenshots.
- The expanded citation table exposed a keyboard-accessibility issue in its horizontal scroll container. Added a focusable, named region, then repeated browser validation; modal cleanup is also guaranteed in the test runner after failures.

User-requested parallel tasks: index timestamp implementation and browser/test updates delegated; root integrated the deck narrative, figures and metadata. No commit, push, deployment, raw-data processing, external dependencies or hooks added. Testing remains local Chromium, not a claim about other browsers or deployed state.

## First iteration record (superseded layout)

Local review: 2026-09-12. Starting HEAD `767ed56643ce1d271120788b96f0744918788216`, with pre-existing uncommitted report/data work preserved. Reviewed URL: `http://127.0.0.1:5173/`; this is not a deployment review. Release `oa-2026-06-26-1f41fe8f2476`; OA 2026-06-26, RW 2026-09-10.

## Delivery

- Installed `.agents/skills/html-ppt-skill` from `lewislulu/html-ppt-skill`, commit `f3a8435d3901697d5ac5e64d356c933637e43107`, with the skill-installer archive helper. Initial sparse Git installation failed to find root SKILL.md; download installation succeeded. Compared installed files against the pinned Git archive: identical. No third-party hooks executed.
- Chose `academic-paper` and the supplied starter / cover, two-column, three-column and chart-bar patterns, adapted to the existing report's restrained typography. Uses upstream local base/theme/runtime, not a new React or chart stack. CDN fonts and Chart.js omitted; charts are static semantic HTML/SVG with accessible tables and exports.
- Homepage has exactly three publication choices. `#/report-v1` retains the old RW application; `#/snapshot/overview?sources=rw%2Coa` retains v2; `presentation-v2/index.html` opens the deck. Explicit `.html` avoids Vite dev's directory fallback to the React index.
- Ten slides cover research question, populations, screening, annual counts, OA primary domains, classification methods, collaboration completeness, fixed-window citations, author identity and limitations. This is a curated summary, not every analysis in v2.
- Direction keys, selector, buttons, deep links, fullscreen, presenter popup, evidence dialog and aggregate export are available. Inactive slides are inert. Long mobile slides scroll vertically; the annual chart scrolls horizontally rather than shrinking labels illegibly.

Files added: `src/ReportIndex.jsx`, `src/report-index.css`, `scripts/build-presentation.mjs`, `scripts/check-presentation-browser.mjs`, `tests/presentation.test.mjs`, `public/presentation-v2/` and the installed skill. Wiring/documentation edits: `src/main.jsx`, `src/report/ReportChrome.jsx`, `package.json`, `README.md`, `DESIGN.md`, `.agents/skills/README.md`.

## Evidence contract

`npm run build:presentation` validates published chunk size, SHA-256 and schema before rendering. `npm run build` includes this step. Full chart contracts are embedded only for the five displayed figures; the modal/export retains original row values, n/N, units, scope, dates, limitations, chart/slice IDs and release. No raw-source scans or statistical processing are introduced.

| Slide | File | Chart / slice |
|---|---|---|
| Source paths | overview.json | population-accounting / mixed_diagnostic-default |
| Screening | overview.json | screening / A0-screening |
| Time | time.json | T1 / B-retracted |
| Main domains | fields.json | F1 / A1-primary-domain |
| Cooperation | geography.json | G2 / A1-collaboration-institution_country |
| Citations | citations.json | C4 / C-incoming-common_5y |

Source-path counts are separate overlapping populations, not a union. Screening uses the flagged-record denominator, not all publications. Annual partial-year status, missing domain labels and common five-year follow-up eligibility remain explicit. The author note does not process or adjudicate identities. Original report source/slice behavior, validation, charts, tables and exports are untouched.

## Actual checks and screenshots

- `npm run build`: passed; public-data guard passed at 2,016,328 bytes, 36 samples. Existing >500 kB bundle warning remains.
- `node --test tests/presentation.test.mjs tests/snapshot-*.test.mjs`: 62 passed.
- `sha256sum -c /tmp/sro-ppt-contracts.sha256`: all existing `public/data` and `pipeline` files unchanged from this task's starting state.
- `git diff --check`: passed.
- Browser runner: five groups passed, no page errors. Verified index/v1/v2 navigation, RW/OA/joint overview, existing topic deep link, all five evidence links, keyboard navigation, exact export equality, modal dismissal and presenter popup. No external HTTP requests from the deck.
- Chromium screenshots and axe checks at 1440×900, 768×1024, 390×844: all ten slides plus index passed the configured WCAG A/AA rules. Automated checks are not a complete accessibility certification.

Before screenshot: `/tmp/sro-index-before.png` (original RW landing page). New deck has no previous version to compare.

Initial review: `/tmp/sro-presentation-review/`. Fixed explicit HTML path, chart-ID-qualified topic links, keyboard event handling and mobile annual-axis readability before confirmation.

Confirmation: `/tmp/sro-presentation-confirm/checks.json`; screenshots `desktop-index.png`, `tablet-index.png`, `mobile-index.png`, `{desktop,tablet,mobile}-slide-{1..10}.png`, `desktop-evidence.png`, `presenter.png`. Inspected individual representative figures and all-slide contact sheets `desktop-contact.png`, `tablet-contact.png`, `mobile-contact.png`. Additional mobile bottom screenshots confirm long-slide content and recent-year chart access.

Reproduce browser checks using the existing local tools:

```bash
PLAYWRIGHT_MODULE=/tmp/snapshot-browser-check/node_modules/playwright/index.mjs \
CHROMIUM_PATH=/home/ider/.cache/ms-playwright/chromium-1169/chrome-linux/chrome \
AXE_PATH=/tmp/snapshot-browser-check/node_modules/axe-core/axe.min.js \
REPORT_QA_OUT=/tmp/sro-presentation-confirm \
node scripts/check-presentation-browser.mjs
```

## Boundaries

Presenter mode requires popup permission and a browser supporting its runtime features. Mobile uses scrollable reading pages, not tiny fixed-ratio slides. No Safari/Firefox, physical-device or deployed-site testing was performed. No commit, push or deployment performed. Existing dirty data/pipeline changes belong to earlier work and are not part of this presentation task.
