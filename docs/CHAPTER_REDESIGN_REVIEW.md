# 章节阅读体验：第二轮交付记录

本轮以用户验收的概览为样板，推广其余八章。仅修改本地工作树，不提交、推送或部署。第一轮的历史记录保留在 `OVERVIEW_REDESIGN_REVIEW.md`。

## 范围与基线

- 基线 HEAD：`2630447267d4c8daf3311880008863b4fe02ee38`。
- 本轮实际浏览器地址：`http://127.0.0.1:4173/#/snapshot/…`；没有检查部署站点，不以本地截图声称线上已更新。
- 公开 release：`oa-2026-06-26-0d8f97ed1bf5`；OpenAlex 2026-06-26，RW 2026-09-10。没有修改 manifest 或聚合文件。
- 遵循仓库 `research-report-design` skill，检查网站设计、统计规范、manifest 与已有组件。未找到适用的 AGENTS.md；未安装 Impeccable、web-design-guidelines、Playwright skill。实际使用已有 Playwright 库、Chromium 和 axe-core，没有安装依赖或 hook。
- 改造前本地截图覆盖八章桌面与手机；基线审查显示来源控件、分析索引与长方法先于证据。继续采用已验收的单栏方案，不增加永久侧栏；两个低成本布局方案与取舍见 `DESIGN.md`。

## 变更文件

| 文件 | 职责 |
| --- | --- |
| `src/report/ReportChrome.jsx` | 概览和各章共用刊头、折叠章节目录、可见来源和日期 |
| `src/report/ChapterReport.jsx` | 八章的研究问题、阅读顺序、来源/分析探索区、方法与章节入口 |
| `src/report/ResearchFigure.jsx` | 证据绑定的观察、图、图注、详细方法、无障碍表和导出 |
| `src/report/chapter.js` | 章节引言、随切片更新的观察、单位说明、n/N 与证据标识 |
| `src/report/ReportFigure.jsx` | 推广 Figure/Caption，保留概览代表图 |
| `src/report/OverviewReport.jsx` | 复用共用刊头和范围组件；原概览行为不变 |
| `src/report/SnapshotReport.jsx` | 接入章节布局，复用原 Plot、G1 指标变换与 CSV Export |
| `src/report/DisciplineExplorer.jsx` | 保留完整两层树；分布/时间图共用 Figure；详细方法移至图后 |
| `src/report/overview.css`、`src/report/chapters.css` | 共享出版物 token、响应式章节和图形样式，不影响旧 RW 站点 |
| `tests/snapshot-chapters.test.mjs` | 四项新增测试，遍历所有切片的数据、来源、文案与图形契约 |
| `scripts/check-chapters-browser.mjs` | 逐章来源、106 个深链接及 CSV、截图、可访问性和学科交互检查 |
| `scripts/check-overview-browser.mjs` | 学科导航回归等待可见结果区，而非默认折叠的树 |
| `DESIGN.md`、本文 | 第二轮设计契约、交付和证据记录 |

默认阅读顺序为研究问题、简明来源范围、当前已发布观察、主图；详细方法和高级切片选择折叠。第一条观察来自当前切片，其他已发布观察仍可展开。没有把所有图形替换成横条或卡片：年度线图、联合维度矩阵、散点、区间和控制图保留原有统计表达与交互。

学科默认保留 Subjects、Topics、Concepts 三种入口、完整主/子学科树与分布/年度图。节点总量与覆盖先呈现；树是次级索引，不再占据整段默认阅读路径。Concepts 历史父级、多父级不可加总和匹配总体的截止边界仍在可见区说明。

## 逐章契约

| 章节 | 原有切片数 | 重点保留 |
| --- | ---: | --- |
| 时间与观察期 | 12 | 发表年/撤稿年区分、近期随访、同比未定义、原线图和矩阵 |
| 学科与主题 | 24，另有学科树 | 分类不混合、主/子层、缺失组、n/N、Top N 不缩分母 |
| 撤稿原因 | 8 | 原因多标签、完整组合、程序与实质原因、映射审计 |
| 地理与合作 | 12 | 署名地址非国籍、五种计数方式、分数权重、合作矩阵 |
| 机构与作者 | 15 | 作者 Top N 表、身份链接、署名非责任、集中度 |
| 期刊与出版 | 17 | 论文/来源/出版商区分、发文分母、控制图政策 |
| 引用与持续传播 | 9 | 累计引用/撤稿后引用、时间可判定边、零引用、各年度有效 N |
| 数据与方法 | 9 | 匹配状态、来源依赖、回溯验证缺口、完整 manifest |

以上 106 项加概览原有三项均保留。每章的 RW、OA、联合选择仍调用原 `filterCharts` / `sourceProfile`，不是相加后的并集。无可用来源/切片显示未提供，不使用零或其他来源替换。

数据表和 CSV 仍保留原 release、chart/slice、population、metric、scope、日期、截止、方法、行内 n/N/value/unit；显示舍入不改变 CSV 精度。CSV 原有公式注入保护也保留，包括负号前的安全前缀。数据校验、路由解析、统计计算、公开文件与流水线无变更。

## 实际检查

- `npm test`：51 项 Python 测试通过，预期负向发布日志不算测试失败。
- `node --test tests/snapshot-*.test.mjs`：30 项通过，包含新增四项。
- `npm run build`、`npm run check:data`：通过；public/dist 均为 1,895,280 字节，仅聚合和 36 条样本。
- `git diff --check`：通过；公开数据、pipeline、schema、来源规则、学科计算与旧入口未改动。
- 浏览器最终确认：44 组全部通过，无未捕获页面错误，106 个切片 CSV 全部核对通过。Chromium 136.0.7103.25；三个视口为 1440×900、768×1024、390×844，八章默认页均截图并运行 axe WCAG 2/2.1 A/AA 自动检查，无整页横向溢出。
- 每章真实切换 RW → 联合 → OA → 联合，核对可用分析集合及当前切片；逐个打开 106 个明确深链接，比较当前观察、来源、单位、截止并下载 CSV，逐行核对 n/N/value/unit 与来源元数据。
- G1 五种计数方式联动检查；三种学科分类进入子层，切换全部可用指标并核对时间/分布导出；时间点键盘锁定/取消、切片切换、后退、刷新与不兼容来源检查。
- 概览原回归脚本 11 组通过，包含三种尺寸、来源切换、三个深链接、精确导出、键盘/触摸、复制链接失败回退和 200% 字号。

可复跑命令（本地开发服务器需已启动）：

```bash
export PLAYWRIGHT_MODULE=/tmp/snapshot-browser-check/node_modules/playwright/index.mjs
export CHROMIUM_PATH=/home/ider/.cache/ms-playwright/chromium-1169/chrome-linux/chrome
export AXE_PATH=/tmp/snapshot-browser-check/node_modules/axe-core/axe.min.js
REPORT_QA_OUT=/tmp/sro-chapters-review/confirmation node scripts/check-chapters-browser.mjs
REPORT_QA_OUT=/tmp/sro-chapters-review/overview-regression node scripts/check-overview-browser.mjs
```

首轮集中检查发现跨章节保留了探索区展开状态，以及学科方法披露挤占图形前空间。集中修复后，章节切换关闭探索区，学科详细方法移到图后。检查脚本另修复了原 CSV 安全前缀的预期值与嵌套 summary 的严格定位；未为通过测试改导出逻辑。应用布局没有再循环润色。

## 截图证据

本机目录 `/tmp/sro-chapters-review/`：

| 阶段 | 路径规则 |
| --- | --- |
| 本地改造前 | `before/{chapter}-desktop.png`、`before/{chapter}-mobile.png`（全页；没有补造平板前图） |
| 首轮审查 | `review/{chapter}-{desktop,tablet,mobile}.png` 及 `-full.png`、`checks.json` |
| 修复后视觉确认 | `after/{chapter}-{desktop,tablet,mobile}.png` 及 `-full.png` |
| 最终浏览器结果 | `confirmation/checks.json` 与同目录三个尺寸、学科子节点截图 |
| 概览回归 | `overview-regression/checks.json`、三个尺寸及来源/深链接/字号截图 |

`chapter` 为 `time`、`fields`、`reasons`、`geography`、`entities`、`publishing`、`citations`、`quality`。例如前后对比：`before/time-desktop.png` 与 `after/time-desktop-full.png`；手机学科对比：`before/fields-mobile.png` 与 `after/fields-mobile-full.png`。

实际打开审查包含改造前时间桌面、学科手机、引用桌面；改造后时间全页、学科桌面/手机全页、原因桌面、地理手机、机构桌面、期刊平板、引用全页与质量平板。图形与原始表格仍可局部滚动。部分截图的金色标题框是原路由聚焦反馈，不是装饰性卡片。

## 限制与待验收

- 未运行 Firefox、Safari 或人工屏幕阅读器检查；axe 通过不等于完整无障碍认证。未做打印/PDF 验收。
- 数据密集的学科树、长条形列表和矩阵保留局部滚动，避免强行压缩标签；手机学科页的主图仍在来源与节点统计之后，需要继续向下阅读。
- 原旧入口构建仍有大于 500 kB 的 chunk 警告，本轮没有迁移技术栈或改动旧 v2 打包。
- `/tmp` 截图不会进入网站资源或自动上传，清理临时目录会删除证据。视觉和阅读效果仍交用户最终验收。
- 本轮没有补充任何未发布统计，也没有消除历史传输证据缺口；全部修改保持本地，未提交、推送或部署。
