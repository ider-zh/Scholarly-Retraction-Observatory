# Chart selection and encoding

Choose the chart from the analytical question and available aggregate granularity. The variety of charts is not itself a quality metric.

## Selection matrix

| Question | Default candidate | Important constraint |
|---|---|---|
| How did recorded counts change by year? | Columns; lines for supported continuous comparisons | Separate publication year and retraction year; mark partial periods |
| How do two time definitions differ? | Aligned small multiples | Align units/scales when a comparison is intended; do not invent event dates |
| Which known entities have the most linked papers? | Sorted horizontal bars or dots | Counts are associations, not responsibility rankings |
| How does publication volume relate to a retraction proportion? | Scatterplot with highlighted examples | Require compatible n/N, adequate base size, and explicit time window |
| Does rank change after normalization? | Slopegraph or paired dot/rank chart | Match the ranked universe and explain ties and missing denominators |
| How is publication year related to event year? | Cohort heatmap | Treat unobserved future cells differently from observed zeros |
| How long until retraction? | Histogram; ECDF if supported | Identify the included cohort; avoid selection-biased causal claims |
| How do delay distributions differ by field? | Median and IQR dot-range, or boxplot when supported | Do not call IQR a confidence interval; show N |
| What reasons are recorded? | Multi-label horizontal bars | Shares may exceed 100%; explain the denominator |
| Which reason combinations recur? | UpSet-style combination chart | Use exact combination aggregates; do not infer intersections from marginals |
| How concentrated are linked papers? | Lorenz curve or cumulative share chart | Define ranking population; preserve zero/missing rules |
| How often are papers cited after retraction? | Aligned event-time chart or eligible-window summary | Require valid dates and comparable follow-up; citation is not endorsement |
| What does each source cover? | Labeled matrix or population diagram | A0/A1/B/C are not automatically disjoint or sequential |
| How complete is metadata? | Coverage bars or missingness heatmap | Unknown is not an observed zero |

Only use a chart when the published data actually supports it. A clean table is better than an attractive but reconstructed distribution.

## Visual grammar

Use a functional figure subtitle specifying quantity, units, population, and time. The headline may state a supported observation. This pairing avoids a chart that has a dramatic title but no measurable meaning.

Prefer horizontal labels and direct labeling for a few series. For many categories, reduce emphasis, highlight selected groups, or use small multiples. Avoid rainbow coloring where hue has no semantic role.

Use zero baselines for ordinary magnitude bars. A line or scatterplot can have a restricted domain when it is clear and not misleading. State log scales plainly and define how zeros are represented. Never add epsilon to published data silently.

Do not use 3-D effects, decorative perspective, or a second y-axis merely to make two unrelated series appear correlated. Do not use maps where a rank comparison is the actual reader task.

Legend, axis, label, tooltip, narrative, table, and export must agree about units. Percentages and per-10,000 values must not share an unlabeled axis.

## Annotation policy

Usually one primary annotation and at most two supporting annotations per chart. Pin them to actual values or verified events. An event line needs a source. Prefer an annotation that explains the comparison, not one that restates every point.

Disable decorative chart entrance animation during visual tests. Honor reduced-motion settings for users. Do not animate every data value to imply live monitoring of a fixed snapshot.

## Evidence binding

Treat figure text and data as a unit:

```text
release + population + chart_id + slice_id + metric + scope
   → plot + headline + observation + sample size + notes + export
```

Tests must change the source and slice, then verify that this whole unit changes together. If a filter makes the authored observation invalid, produce a neutral description of the selected view rather than leaving the old headline.

## Specific integrity checks

Full and fractional counting need explicit labels. Filtering a display must not silently renormalize existing fractional weights. Preserve the pipeline's treatment of missing institutions and unknown affiliations.

Do not call a share within a retraction dataset a retraction rate. Do not present recent publication cohorts as safer without considering their shorter observation period.

Treat existing source definitions and validated manifests as the authority for this project. A design skill must not silently "fix" a disputed count or broaden a population.
