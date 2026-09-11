# Layout and visual system

These are proposed project defaults, not universal rules or a claim that the current site passes them.

## Information architecture

Use two reader modes conceptually:

- **Read the report:** a short, curated sequence of findings, charts, explanation, and limitations.
- **Explore the data:** source/slice selection, alternative metrics, comparison, export, and detailed tables.

The distinction need not introduce a new router or dependency. Resolve implementation against the existing route parser first. An explicit old `slice` link should still take a reader directly to that analysis.

A useful overview order:

```text
Site identity                     Research report / Explore / Methods

Research question
Two-sentence introduction
Compact scope: dataset role · unit · source dates · release

Primary observed finding (only when supported)
Dominant chart + functional subtitle + one relevant annotation
Short interpretation + one prominent boundary

Two further findings or chapter entry summaries
Each: question → evidence → interpretation → link to analysis

Sources, coverage, method details, reproducibility
```

Do not make a giant hero, stock image, or ornamental animation displace the main evidence. A diagram of source populations can be the lead visual when the central question is scope, but overlapping populations must not be drawn as an additive funnel.

## Navigation and control density

Use one source selector, preferably compact, adjacent to the current scope summary. Explain the joint-source role in one visible sentence. Put the longer provenance explanation behind a labeled detail link.

For the same chart-choice task, choose one of a contextual index or a select control at a given breakpoint. Previous/next controls can remain in the explorer when they provide a real reading sequence. Do not stack every navigation affordance in the default report view.

One optional on-page contents column may be useful on wide screens. Avoid an always-visible site sidebar plus another wide chart sidebar that squeezes the plotting region.

## Project starting targets

| Element | Suggested starting value | How to validate |
|---|---|---|
| Maximum reading layout | 1,200–1,280 px | Wide enough for labeled charts, not wall-to-wall prose |
| Long-form paragraph measure | About 32–40 full-width Chinese characters | Check actual CJK fonts; `ch` is not a Chinese-character unit |
| Body text | 16–18 px, line height 1.65–1.85 | Read Chinese and mixed English at normal zoom |
| Main title | 36–44 px desktop, 28–34 px mobile | Wrap naturally; no isolated punctuation line |
| Chart axis/legend | Prefer 12–14 px at rendered size | Do not merely shrink a wide SVG on mobile |
| Source/caption text | Prefer at least 12–13 px | Secondary does not mean unreadable |
| Section rhythm | 48–72 px for major transitions | Differentiate a section break from a label gap |
| Primary chart | Roughly 360–460 px high on desktop | Choose by labels and marks, not a fixed dashboard grid |

Choose values through rendering, not blind adherence to this table. At 1440×900, the first chart's plotting region should begin in the initial viewport. At 390×844, the initial viewport should explain the question, current scope, and primary finding without requiring a filter choice.

## Typography and color

Use a robust Chinese system font stack unless the project deliberately provides appropriately licensed fonts. A second face for editorial headings is optional, not a requirement. Test fallback fonts; do not depend on an external font request for readable geometry.

Create named tokens for surfaces, ink, secondary text, borders, source identities, highlights, and missing-data states. Keep a small semantic palette; colors should mean the same thing on every page. A source color and an uncertainty color must not silently swap roles.

For this research publication, start with a light neutral reading surface, dark ink, restrained source colors, and subtle dividers. This is a deliberate project direction, not a ban on dark mode or particular fonts.

Use color with labels, line styles, or shapes where the distinction matters. Do not use red to imply misconduct or green to imply innocence.

## Containers and density

A figure can sit directly in the report flow. Reserve cards for independent interactive blocks, not every paragraph. Prefer spacing and type to multiple layers of borders, colored left rails, pill badges, and shadows.

Keep the factual source/date/scope statement visible. Move repeated long definitions and implementation identifiers to details. Retain the single limitation that could change a reader's interpretation immediately next to the finding.

## Responsive behavior

- Reflow long labels for bar charts; show the full label outside the mark region when needed.
- Reduce tick density, not data density or semantic distinctions.
- Allow a labeled, keyboard-accessible scroll region for genuinely wide matrices. The entire page must not overflow horizontally.
- Essential values and context must be available on touch and keyboard, not only hover.
- A print layout should remove interactive chrome and retain chart titles, notes, sources, and dates; do not promise PDF export unless implemented and tested.
