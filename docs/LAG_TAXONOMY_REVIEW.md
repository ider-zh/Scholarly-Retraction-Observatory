# 撤稿时滞图与独立学科章节

## 本轮范围

本地工作树更新，基线 `767ed56` 加此前尚未提交的报告改造。使用项目 `frontend-design` 和 `research-report-design` 约束，未更换技术栈或安装新依赖；未提交、推送或部署。

## 时滞图为何难读，以及如何改造

原图把累计比例画成一条点线，横轴使用天。最大已发布时滞达到 29,622 天，约 81.10 年；大部分变化挤在左侧，读者还需要先理解“累计比例”。完整范围的截图见 `/tmp/sro-lag-taxonomy/before/desktop.png`、`mobile.png`。

比较两个方案：保留累计曲线、默认截断横轴；或者用已有分位时间作为阅读主图、完整曲线作进阶补充。采用后者，避免读者把截断图误认成完整分布，也不从采样的累计点推算新时间段。

主图现在按“把已撤稿论文的等待时间从短到长排列”的读法，展示四条时间条：

| 样本排序位置 | 原始分位时间 | 展示年数 |
|---|---:|---:|
| 四分之一（25%） | 153 天 | 约 0.42 年 |
| 一半（50%，中位数） | 490 天 | 约 1.34 年 |
| 四分之三（75%） | 1,058 天 | 约 2.90 年 |
| 九成（90%） | 2,193 天 | 约 6.00 年 |

四行都从 0 起算、共用线性时长比例；不是四个互斥计数组，不能相加。中位数用既有青色强调，并明确不是平均时间。年数仅按 365.25 天换算和显示舍入；天数来自已发布 `T4/B-default.quantiles`，没有从曲线重估分位数。

按钮支持点击、触摸、Tab、上下方向键；解释跟随所选分位点。完整累计曲线、范围滑块、全部采样点、原始数据表和原 CSV 都保留在进阶区域。明确第 90 百分位不是最大时滞，此图也不是全部发表论文的撤稿风险。

桌面三列“排序位置 / 时长 / 精确数值”；移动端每行先展示名称和数值，时间条独占下一行。沿用既有纸面、青色、灰色与中文系统字体，不引入装饰或另一图表库。

## 三个独立顶级章节

- `#/snapshot/subjects`：RW Subject；只呈现 RW 学科树、分布、年度数量和样本内覆盖。无发表论文分母，不开放总体撤稿率。
- `#/snapshot/topics`：OpenAlex Topics；固定现行主题体系，保留主学科/子学科联动及领域、主题、主主题、多标签、发文基数等已发布专题。
- `#/snapshot/concepts`：OpenAlex Concepts（旧体系）；固定旧概念树，保留数量、时间、覆盖与已有比率，以及历史父级和多父级的解释。

顶级侧栏/移动目录单独列出这三个章节，不再列混合“学科与主题”。新章节没有跨体系下拉框；研究总体、指标、主/子学科仍可切换。来源不符合章节要求时显示不可用，并提供显式启用所需来源的链接，不悄悄替换为另一分类。

新章节的树链接、专题弹层、独立专题页、刷新和深链接都保持本章节路径。显式传入冲突 taxonomy 或其他体系的切片时不显示替代结果。旧 `#/snapshot/fields` 及其所有 taxonomy、slice 链接仍可访问原结果，仅作为兼容入口，不占主目录。

## 数据契约与变更文件

三个章节仍读取并验证同一份公开 `fields.json`；校验完成后按体系选择视图，不复制或改写公开数据。证据路径继续指向真实的 `data/snapshot/fields.json`，没有虚构 `subjects.json` / `topics.json` / `concepts.json`。

主要新增：`src/report/sections.js`、`src/report/LagSummaryPlot.jsx`、`src/report/lag.css`。

接入：`SnapshotReport.jsx`、`ChapterReport.jsx`、`ReportChrome.jsx`、`DisciplineExplorer.jsx`、`TopicAnalysis.jsx`、`TopicIndex.jsx`、`topics.js`、`routes.js`、`chapter.js`、`ReportGuide.jsx`、`ResearchFigure.jsx`、`OverviewReport.jsx`。测试新增 `tests/snapshot-sections.test.mjs`、`scripts/check-lag-taxonomy-browser.mjs`，更新章节单元测试和侧栏检查的章节目录预期。

公开聚合、manifest、原始流水线、来源规则、统计分母、`sources.js`、`discipline.js` 均未修改。版本仍为 `oa-2026-06-26-0d8f97ed1bf5`；OA 2026-06-26，RW 2026-09-10。公开文件仍为 1,895,280 bytes 和 36 个展示样本。

## 实际验证

- `node --test tests/snapshot-*.test.mjs`：41 项通过，含三个章节的数据分区、不变性、真实证据文件路径、来源限制和旧链接。
- `npm test`：51 项 Python 测试通过。
- `npm run build`：构建、公开文件与构建产物数据检查通过。
- `scripts/check-topics-browser.mjs`：26 组通过，109 个专题切片精确 CSV、109 个旧章节深链接。
- `scripts/check-chapters-browser.mjs`：44 组通过，106 个非概览切片精确 CSV，包含三体系节点与指标检查。
- `scripts/check-lag-taxonomy-browser.mjs`：9 组，检查四个分位天数和条长、键盘、完整曲线、原 CSV；三个新章节的 RW/OA/联合来源、节点路径、刷新、弹层、全部平铺切片、冲突路径及旧 fields 链接。
- `scripts/check-sidebar-browser.mjs`：更新为三个独立章节的侧栏和触摸导航检查。

浏览器使用已有 Playwright、Chromium 136.0.7103.25、axe。初审后仅集中缩短重复的图前文字、修正导航测试仍引用旧章节名的问题，再做确认。

截图尺寸为 1440×900、768×1024、390×844。初审 `/tmp/sro-lag-taxonomy/review/`；确认 `/tmp/sro-lag-taxonomy/final/`，包括 `*-lag.png`、`*-lag-dialog.png`、`*-subjects.png`、`*-topics.png`、`*-concepts.png` 和各章 `*-chart.png`。检查详情见该目录 `checks.json`；侧栏确认见 `/tmp/sro-lag-taxonomy/sidebar-final/checks.json`。

## 限制

只验证本地 checkout，未验证部署站点及 Safari / Firefox。旧 fields 兼容入口仍保留原混合体系操作，避免破坏书签；新主目录不再引导至该页。原累计曲线只含已发布采样点，不据其连线计算新时点比例。原 RW 入口包体超过 500 kB 的既有构建提示未在本轮处理。
