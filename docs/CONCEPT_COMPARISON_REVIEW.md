# Concepts annual comparison

## Proportion follow-up

The count-only behavior below is superseded: both the 19-root comparison and
the selected root's complete child comparison now support `metric=proportion`.
The visible comparison-level count/proportion control shares the existing URL
metric with the single-node figures. Titles, axes, legend year readouts, tables
and CSV follow the same selection; source population and node links are retained.

Each percentage is the node's same-publication-year recorded-paper numerator
divided by that node's same-year eligible-publication denominator, multiplied
by 100. `conceptComparison` reuses `disciplineCell`, rather than dividing by the
retracted sample or summing child nodes. OA and matched C_D remain distinct.
RW-only still has no compatible denominator. Share/per-10k remain available in
the original single-node analysis; the comparison's count fallback is explicit.

Percentage axes use the eligible positive data maximum. Small bases (`n < 20`
or `N < 1,000`) and missing values are not plotted or bridged; their true values
and n/N remain in the full table and full-precision CSV. Empty eligible series
show an explanation, not zero curves. Parent links remain navigational, not
conditional intersections. No pipeline or public aggregate changes are needed.

Before screenshots: `/tmp/sro-concept-proportion-before/`; initial review:
`/tmp/sro-concept-proportion-review/`; final confirmation:
`/tmp/sro-concept-proportion-confirm/`. Local checkout at port 5186.

Validation: `node --test tests/*.test.mjs` passed all 91 tests. Vite production
build to `/tmp/sro-concept-ratio-build` and its public-data guard passed
(2,096,986 bytes; existing large-bundle warning remains). Snapshot file SHA-256
checks match the task-start fingerprint. No public data or PPT rebuild was
performed; the production build uses an external temporary directory.

The browser runner checks count/proportion switching, all 19 roots and linked
children, same-year legend and exact CSV n/N/value/eligibility, suppressed-point
geometry, OA and C_D deep links, unavailable RW state, keyboard interaction,
three screen sizes and axe. Desktop/tablet root and mobile child screenshots
were visually reviewed; no layout correction was required after the initial
check. This is local Chromium validation, not a deployed-site review.
Final confirmation passed at all three sizes with zero page errors; its
`checks.json` and 12 root/child count/proportion screenshots are retained in the
confirmation directory. No commit, push or deployment was performed.

## Initial count-only version

Adds two count-only comparison figures beside the existing Concepts analyses:
all 19 real Level 0 concepts, followed by all Level 1 concepts linked to the
selected root. The existing single-node figure and metric controls remain intact.
Selecting a root uses the existing node/parent URL state; the child comparison
also follows an existing deep link to a child. OA and matched C_D populations
use their own published annual counts. RW-only does not substitute a dataset.

All curves are visible initially, without Top N truncation. Legend focus/hover
emphasizes a series; root selection opens the child comparison below. The year
slider shows same-year counts in the legend. Counts use a common linear zero
baseline, which highlighting does not change. Responsive SVG keeps the complete
time axis visible on mobile. Missing values break lines and are not zero-filled;
the incomplete final year has open markers.

Concepts are overlapping labels. Historical parent links select navigation
branches, not parent-conditioned intersections; child counts cannot be summed
into root counts. Missing/navigation-only nodes are not presented as real subjects.
Tables and CSV retain every displayed subject/year, including zero and missing
values, source population, source cutoffs and scan/tree provenance.

Implementation: `src/report/ConceptComparison.jsx`, `conceptComparison.js`,
`concept-comparison.css`, and the Concepts-only insertion in `DisciplineExplorer.jsx`.
No pipeline, public aggregate, denominator, source rule, dependency or PPT changes.

Validation: 87 Node tests passed; Vite build to `/tmp/sro-concept-comparison-build`
passed (existing large-chunk warning). Public data validation passed. The browser
script checks 1440×900, 768×1024 and 390×844, every root/linked child, keyboard
selection, full-series CSV, OA/C_D and unavailable RW states, deep-link reload,
horizontal overflow and axe WCAG checks. Initial screenshot review prompted a
mobile full-axis fix; the confirming browser run passed with no page errors.
Evidence: `/tmp/sro-concept-comparison-review/confirm/` and its `checks.json`.
Local checkout at `http://127.0.0.1:5186/`; no commit, push or deployment.
