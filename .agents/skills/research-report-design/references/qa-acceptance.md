# QA and acceptance

## Evidence levels

Report checks as `passed`, `failed`, `not_run`, or `not_applicable`. `Not run` is not a pass. A screenshot's existence is not proof that the screenshot was inspected.

Maintain one bounded review cycle: capture all required viewports/states, fix the findings in a batch, and make one confirming pass. Escalate remaining problems explicitly rather than running endless self-polishing loops.

## Required baseline

Record reviewed Git commit, deployment URL or local URL, release ID, source dates, chosen sources, chosen slice, browser, and viewports.

Capture at least 1440×900, 768×1024, and 390×844. The included Python script is an optional capture helper. An installed browser skill or existing Playwright setup is equally acceptable.

Test source modes RW-only, OA-only, and joint, where supported. Test the initial overview plus at least one deep-linked slice, one changed selection, and one legitimate unavailable/empty state. Do not modify production data to create those states.

## Visual review

- Does the first desktop viewport show the question, scope, a supported finding, and the beginning of the primary chart?
- Does the initial mobile viewport communicate the same hierarchy without requiring a control choice?
- Is the plotting region wide enough for real Chinese and English labels?
- Are axes, legends, sources, and notes readable at normal zoom?
- Is there one obvious navigation path rather than several competing controls for the same task?
- Are borders, colors, and cards used to distinguish meaning rather than decorate every block?
- Does the page avoid global horizontal overflow? A labeled local matrix scroll area is allowed.
- Check long institution names, unavailable metadata, zero values, and small denominators.
- Inspect at 200% zoom or equivalent enlarged text; do not rely solely on a narrow viewport check.

## Interaction and accessibility

Use keyboard and actual pointer/touch inputs. Check focus visibility, source selection, history/back, deep links, disclosure controls, table access, export, and copy-link success/failure. Verify that critical observations do not require hovering.

Reduced-motion settings must be honored. Long-running animation must not block reading. Use a contrast checker or an appropriate audit tool; do not claim contrast compliance from visual judgment alone.

## Data regression

Before and after presentation-only changes, compare public aggregate content and published metadata. Where outputs are rebuilt, explain any diff. Verify formula consistency from the same published n/N and units used by the chart.

Check that switching sources/slices updates narrative and export alongside marks. Unavailable data must not become zero; mixed source populations must not become a sum; unchanged fractional weights must remain unchanged.

## Project commands

Read the current `package.json` first. At the reviewed checkout, commands included:

```bash
npm run build
npm run check:data
npm test
```

The build already invokes the public-data check in that checkout. State exactly what actually ran; do not invent `lint`, TypeScript, or test scripts that do not exist. Adding tests or tooling requires an explicit, minimal change.

## Deliverable record

```text
Status: passed / failed / pending visual review
Reviewed commit and release:
Routes and source/slice states:
Commands actually run and results:
Before/after screenshots inspected:
Data/contract regression results:
Accessibility checks and tool used:
Known limitations and unresolved defects:
```

A beautiful screenshot does not prove correctness; a clean build does not prove beauty.
