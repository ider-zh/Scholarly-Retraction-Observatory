# 概览阅读体验：第一轮交付记录

状态：第一轮本地实现与检查通过，交付时未提交、推送或部署；用户随后授权提交并推送本轮改造。第二轮章节推广未执行，线上部署结果另行确认。

## 版本、范围与 skill

- 检查基线 commit：`d035224b86a8e4716afdbceea858b52bc9918eea`；本轮为该提交之上的本地工作树变更。
- 本地目标：`http://127.0.0.1:4173/#/snapshot/overview?sources=rw%2Coa`。
- 线上基线：`https://scholarly-retraction-observatory.9992099.xyz/#/snapshot/overview?sources=rw%2Coa`，实际浏览器成功打开并截图；没有从外观推断线上 Git revision。
- 本地公开数据 release：`oa-2026-06-26-0d8f97ed1bf5`；OA 截止 2026-06-26，RW 截止 2026-09-10。没有改动 manifest。
- 未找到适用的 `AGENTS.md`。已阅读网站设计、统计规范、v2 RESEARCH、manifest、报告组件、路由、校验与样式；规范中规划能力没有当成已完成能力。
- 解包来源：`/tmp/tmp/codex-research-report-skills.zip`；SHA-256 `d3663feb1d50fe9c841c49974d5830c1f89ac0b19632f4c0b1bea081c18f4dbd`。九个 skill 文件放入 `.agents/skills/research-report-design/`；没有覆盖项目规范或安装附带建议的第三方 hook。
- 实际读取并遵循 `research-report-design` 及其布局、编辑、图形、参考、QA 文档。未找到 Impeccable、web-design-guidelines、Playwright skill；没有声称调用它们，也没有联网安装。实际浏览器检查使用已有 Playwright 库、Chromium 和 axe-core。

## 本轮变更

| 文件 | 责任 |
| --- | --- |
| `.agents/skills/research-report-design/` | 用户提供的 skill、参考资料与可选脚本；未执行其安装建议或截图脚本 |
| `DESIGN.md` | 基线审查、两个线框方案、选定的单栏结构、设计 token、数据与路由契约 |
| `src/report/SnapshotReport.jsx` | 仅增加概览分支；复用原校验、来源切换、CSV 导出及旧图表组件 |
| `src/report/OverviewReport.jsx` | 研究问题、来源范围、绑定数据的发现、折叠探索与方法、章节入口 |
| `src/report/ReportFigure.jsx` | 代表图、图注、交互、无障碍表与证据标识 |
| `src/report/overview.js` | 精确切片选择、观察句与证据单元绑定、展示排序 |
| `src/report/overview.css` | 仅作用于概览的浅色出版物布局与响应式样式 |
| `tests/snapshot-overview.test.mjs` | 新增三个单元测试，检查来源、切片、动态文案、空值与数据不变性 |
| `scripts/check-overview-browser.mjs` | 可复跑的浏览器状态、截图、导出及可访问性检查，无新增依赖 |
| `docs/OVERVIEW_REDESIGN_REVIEW.md` | 本交付记录 |

默认主图使用已经发布的 `screening/A0-screening`。选择 OA 或两库时，先显示“标记不等于原论文”的研究问题、来源日期和 50,331 / 114,538（43.94%）的观察，再显示各互斥筛选组的横条。只改显示顺序，不改值或分母。标题疑似通知仍标为规则筛查，未声称逐篇确认。

研究范围核算与文献类型图仍能由原 `slice` 链接或折叠选择器访问；它们没有在本轮全部改造成新 Figure。默认没有同时露出侧栏、快捷按钮、下拉框和上一项/下一项。详细定义、角色筛选、来源依赖、回溯验证缺口均可展开查看。关键比率限制与观察日期保留在图附近。

## 实际执行的检查

| 检查 | 结果 |
| --- | --- |
| `npm test` | passed：51 项 Python 测试；负向发布测试按预期输出拒绝无效 manifest 的错误日志，整体退出 0 |
| `node --test tests/snapshot-*.test.mjs` | passed：26 项 Node 测试，包含新增 3 项 |
| `npm run build` | passed；生产包及 public/dist 数据门槛通过 |
| `npm run check:data` | passed；public/dist 数据均 1,895,280 字节，仅聚合与 36 条样本 |
| `git diff --check` | passed |
| `git diff --quiet -- public/data pipeline src/report/schema.js src/report/sources.js` | passed：公开数据、流水线、校验及来源规则没有改动 |
| 浏览器确认 | passed：Chromium 136.0.7103.25，11 组检查，无页面脚本错误 |
| axe WCAG 2/2.1 A/AA 自动规则 | passed：三个尺寸、RW/OA、展开数据表及 200% 字号状态；不等同于完整人工无障碍认证 |
| Firefox / Safari / 屏幕阅读器人工检查 | not_run |
| 打印或 PDF 验收 | not_run；有基础打印样式，不声称具备 PDF 导出 |

浏览器执行命令（依赖本机现有工具路径，没有修改 package.json）：

```bash
PLAYWRIGHT_MODULE=/tmp/snapshot-browser-check/node_modules/playwright/index.mjs \
CHROMIUM_PATH=/home/ider/.cache/ms-playwright/chromium-1169/chrome-linux/chrome \
AXE_PATH=/tmp/snapshot-browser-check/node_modules/axe-core/axe.min.js \
REPORT_QA_OUT=/tmp/sro-overview-review/after \
node scripts/check-overview-browser.mjs
```

检查包含：RW → 联合 → OA → 联合切换；全部三个原有概览深链接；选择器切换、刷新与后退；失效切片、来源不兼容和无效 sources；悬停、键盘锁定/取消/方向键、移动端真实触控；完整数据表；筛选与文献类型两种 CSV 的切片、指标、来源、日期与原始精度；复制链接成功和拒绝时的回退；章节目录进入现有学科树后返回；实际字号放大为 200%（不是仅截图缩放）。

先集中截图检查一次，发现旧 CSS 的底色/字号覆盖以及浏览器 CSSOM 对百分比字符串的序列化舍入。修正概览选择器隔离、图注顺序，并将视觉宽度断言设为小于 0.0001 个百分点的渲染容差；CSV 仍检查原始数值 `43.942622`，没有改聚合数据或降低导出精度。随后一次完整确认通过，没有继续循环视觉润色。

## 前后截图与审查结果

实际打开检查了三个尺寸的首屏与全页、线上基线、RW/OA 状态、旧文献类型深链接、200% 字号全页。截图保存在本机临时目录，不进入 public 数据或部署资产。

| 尺寸 | 本地改造前 | 本地确认后 |
| --- | --- | --- |
| 1440 × 900 | `/tmp/sro-overview-review/before/desktop.png` | `/tmp/sro-overview-review/after/desktop.png` |
| 768 × 1024 | `/tmp/sro-overview-review/before/tablet.png` | `/tmp/sro-overview-review/after/tablet.png` |
| 390 × 844 | `/tmp/sro-overview-review/before/mobile.png` | `/tmp/sro-overview-review/after/mobile.png` |

同目录的 `desktop-full.png`、`tablet-full.png`、`mobile-full.png` 为全页。线上基线为 `before/deployed-desktop.png`；确认后的 `rw.png`、`oa.png`、`deep-link.png`、`text-200-full.png` 与 `checks.json` 保存其他状态及机器检查结果。首轮待修复截图与结果另存 `review/`，不冒充最终确认。

桌面图形区从页面约 709 px 开始，首屏能看到主图；手机首屏能读完问题、来源日期与主要发现，图形接续在下方。三个尺寸无整页横向溢出。默认页全高从约 2,812 / 3,009 / 4,355 px 变为 2,068 / 2,099 / 2,647 px。表格仍允许带标签的局部横向滚动。部分初始截图中的金色标题框是路由自动聚焦后的可见焦点，不是装饰边框；交互控件也保留焦点反馈。

## 保留的契约与待验收项

- 未改公开 JSON、manifest、统计数值、分母、来源纳入规则、角色策略、离线流水线、hash 参数解析或其他章节结构；所有原有概览 slice 均可访问。
- 概览无 slice 时只调整代表图的默认选择；明确 slice 不回退到另一张图。无效来源/切片不显示旧发现。
- 沿用原 `Export`：CSV 包含 release、chart/slice、population、metric、scope、两份来源日期、观察截止、方法与逐行 n/N。显示舍入不改变 CSV 精度。
- “RW + OA”仍是可用分析集合，不是并集总量。RW-only 原来没有已发布的概览图，本轮明确展示未发布状态并引导到 RW 时间/学科分析；没有从两库核对图偷取一个数字伪装成单库图。
- 非代表图继续沿用旧组件和部分较长说明，其他章节未推广，待第一轮验收后再做第二轮。公开数据契约下缺少的 RW 概览图不能仅靠界面改造补齐。
- 生产构建仍提示原有主入口 chunk 超过 500 kB；本轮不迁移技术栈或改 v2 打包。
- 本地截图位于 `/tmp`，清理临时目录会删除证据；需要长期归档时应另存，不自动上传或部署。
- 第一轮交付时只修改本地工作树，HEAD 未改变；后续提交与推送由用户单独授权。视觉与阅读顺序最终仍待用户验收。
