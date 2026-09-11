# Reference cases and verified skill sources

Reviewed: 2026-09-11. Links are sources and design references, not endorsements of uninspected future code. Recheck upstream instructions before installing; retain a version/commit record. This pack does not vendor third-party skill code, fonts, images, or report data.

## A. Published research/editorial websites

These are design references. They are **not claimed to have been built by Codex or by the recommended skills**.

### Our World in Data — Data Insights

- Format explanation: https://ourworldindata.org/launching-data-insights
- Published feed: https://ourworldindata.org/latest?type=data-insight
- Related explorer example: https://ourworldindata.org/explorers/co2

What to inspect: an observation-led title, one chart, short explanation, and onward data exploration. Borrow the hierarchy of the reading experience; do not clone their entire technical platform or assume their code has the same license as their articles.

Mapping to this project: one report section should answer one question about time, fields, or coverage. Keep the source and methodology accessible without making the reader configure the report first.

### Stanford HAI — AI Index 2025, Research and Development

- Specific chapter: https://hai.stanford.edu/ai-index/2025-ai-index-report/research-and-development
- Index hub: https://hai.stanford.edu/ai-index

What to inspect: a long research publication divided into readable thematic findings, explanatory text, and figures. The 2025 chapter is a chosen reference, not a claim that it is the latest edition.

Mapping: retain the observatory's substantive chapters, but summarize what a reader will learn and provide a consistent path from highlighted findings to supporting analysis.

### The Pudding — Film Dialogue

- https://pudding.cool/2017/03/film-dialogue/index.html

What to inspect: question-led visual explanation and a visible methodology/limitations section. Borrow progressive explanation and the relationship between a claim and its visual evidence, not the entertainment topic or every interactive flourish.

Mapping: use an occasional explanatory sequence for distinctions such as raw counts versus normalized proportions; never fabricate such a distinction in the current data.

### Financial Times — Visual Vocabulary examples

- https://github.com/ft-interactive/visual-vocabulary

This is a chart-reference collection, not a complete website-report template. Use its analytical chart families as inspiration; do not reuse old setup commands as modern dependencies without review.

Mapping: choose ranking, distribution, time, and relationship charts based on the research question instead of turning every aggregate into the same bar chart.

## B. Skill-author demos and example artifacts

### Impeccable

- Upstream: https://github.com/pbakaus/impeccable
- Interactive demos: https://impeccable.style/
- Named case study: https://impeccable.style/cases/neo-mirai/

The author's site presents example interfaces with refinement comparisons and commands such as layout, typeset, distill, critique, and polish. These are first-party demonstrations, not an independently controlled benchmark or a guarantee of the same result on a research report.

The Neo Mirai case study describes a generated visual mock and brand toolkit becoming a responsive conference site, with browser-based fixes for layout, cropping, navigation, and mobile behavior. This is an author-reported implementation case, not a controlled independent evaluation. Borrow the visual-reference → design contract → implementation → browser-review loop, not its expressive conference branding for a research report.

Inspect interface simplification and interaction examples. Evaluate reduction of redundant elements and stronger hierarchy, not only decoration.

### Storytelling Viz Skill

- https://github.com/yudong-94/storytelling-viz-skill
- Examples directory: https://github.com/yudong-94/storytelling-viz-skill/tree/main/viz-example

The README lists examples such as `jobs-held-by-age-sex`, `marriage-by-age-education`, `state-migration-net-balance-2023`, and `japan-prefecture-bump-top6`, with preview HTML and desktop thumbnails. They are self-published skill-output examples, not independently verified deployment outcomes.

This skill targets a single Plotly visualization package, not a React report application. Use the examples to study framing and annotation; do not add Plotly to this project merely to copy them.

## C. Supporting skills

### Impeccable — primary visual-direction skill

- https://github.com/pbakaus/impeccable
- Upstream currently documents `npx impeccable install --providers=codex --scope=project`.
- Hook installation is separate from trusting and running it. Review the installer and hooks before approval; retain existing unrelated configuration.
- Codex invocation: `$impeccable`, followed by the requested action. Do not paste Claude Code marketplace commands into Codex.

### Vercel — web-design-guidelines

- https://github.com/vercel-labs/agent-skills/blob/main/skills/web-design-guidelines/SKILL.md

A UI-code audit skill: useful for accessibility, interaction, and consistency. It is not an art director or a research methods reviewer.

### OpenAI — Playwright

- https://github.com/openai/skills/blob/main/skills/.curated/playwright/SKILL.md

Browser automation guidance for actual rendering and interaction checks. Discover its real installed path; do not assume an old user-wide directory is the current project path. Do not weaken browser or sandbox security merely to obtain screenshots.

### wshobson — data-storytelling

- https://github.com/wshobson/agents/blob/main/plugins/business-analytics/skills/data-storytelling/SKILL.md

A business-analytics narrative skill. Useful for emphasizing an insight and its context. This project's evidence and uncertainty requirements take precedence over persuasive story arcs or compulsory calls to action.

### Alternatives, not compulsory additions

- Anthropic frontend-design: https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md
- UI UX Pro Max: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill

Use one of these instead of, or narrowly alongside, the visual-direction skill only when responsibilities are clearly separated. The latter provides searchable design-system guidance; it does not guarantee a readable scientific argument.

## D. Codex and installer references

- Official skills documentation: https://developers.openai.com/codex/skills/ (redirected to https://learn.chatgpt.com/docs/build-skills during review)
- Skills installer source: https://github.com/vercel-labs/skills

Codex's official documentation identifies repository `.agents/skills` and user `~/.agents/skills` locations. Older skill READMEs and third-party installers may still mention `~/.codex/skills`. This pack uses repository-local `.agents/skills` to avoid that discrepancy.
