# Editorial standard for research web reports

## Page-level structure

Begin with a research question and a brief scope statement. Present the strongest defensible finding early, then the evidence and interpretation. Provide a clear path to methods and deeper exploration.

A useful section unit is:

1. **Question or observed finding:** one sentence, with restrained scope.
2. **Evidence:** a chart with a precise functional subtitle.
3. **Interpretation:** what the displayed comparison means.
4. **Boundary:** what cannot be inferred and why it matters.
5. **Traceability:** sources, date, population, method, table/export.

These are writing responsibilities, not five mandatory colored boxes. Do not display the same headings on every block if that makes the page mechanical.

## Headline examples

The following are patterns, not findings from the current dataset.

Weak: “学科分布分析”
Better question: “哪些学科关联的撤稿论文更多？”
Better observation, only when computed: “按发文规模调整后，部分学科的排序发生变化。”

Weak: “撤稿数据揭示全球学术诚信危机不断加剧。”
Better conditional wording: “在当前来源和截止日期内，某些年份的撤稿记录更多；这不单独证明不端行为发生率上升。”

Weak: “中国作者的撤稿数量……” when the field is affiliation country.
Better: “论文署名机构关联中国的记录……” with the counting mode stated.

Weak: “无数据，所以该领域没有撤稿。”
Better: “该视图尚未发布可比数据；不能据此判断是否存在撤稿。”

## Evidence discipline

Every number in prose must be reproducible from a published aggregate or explicitly cited external source. Keep a machine-readable binding when possible. Do not invent a trend, correlation, causal mechanism, or policy implication to make the report feel complete.

Separate:

- An observation: a property of displayed data.
- An interpretation: what the comparison suggests under stated assumptions.
- An explanatory hypothesis: a possible mechanism requiring additional evidence.
- A recommendation: a normative proposal, not a measured result.

Only use “显著” when a relevant statistical analysis supports it, or explain that it means visually large rather than statistically significant. Usually prefer a concrete magnitude instead.

Avoid “全面揭示”, “毋庸置疑”, “深刻洞察”, generic filler, repeated “值得注意的是”, and unsupported superlatives. Do not turn entity associations into reputational verdicts.

## Captions and disclosure

The visible caption must retain the minimum interpretation contract:

```text
统计单位与指标；总体/样本范围；时间定义与截止日。
如为比例：n/N 与计算倍率。必要时说明缺失或未完整观察。
来源与版本；查看方法 / 数据表 / 导出。
```

This is a content checklist, not a requirement to expose raw field names such as `population_key` in the first reading layer.

Place detailed role screening, merge logic, hash validation, schema identifiers, and extended caveats in accessible disclosures or the methods chapter. Keep the one limitation that most affects interpretation visible next to the result.

## Suggested writing budgets

These are editing targets, not a reason to omit a necessary qualifier:

- Page introduction: roughly 100–180 Chinese characters.
- Primary finding: one sentence.
- Chart interpretation: roughly 80–180 Chinese characters.
- Prominent boundary: one or two sentences.
- Long methods: a separate section with anchors.

A numerical unit and scope can justify a longer sentence. Prefer two readable sentences to a chain of qualifiers connected by many semicolons.

## Dynamic writing

When source selection changes, either recompute narrative from the same aggregate or select a reviewed narrative bound to that exact view. Do not attach one hand-written insight to all slices.

Use “未计算”, “未发布”, “不适用”, “信息缺失”, and “观测为零” deliberately. Do not replace them all with a dash without explaining the legend.

For translated text, preserve the meaning of population, record type, and association. Define acronyms at first use and keep terminology stable across navigation, chart, caption, and export.
