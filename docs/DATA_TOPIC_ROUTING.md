# 数据专题路由与目录

更新：下文记录首次专题路由实现。最新交互以 [阅读与弹层验收](READING_INTERACTION_REVIEW.md) 为准：普通点击卡片打开弹层，目录默认展开且置于“继续阅读”前；原生 href 与独立专题路由仍保留。正文图表也使用专题的数据集与方法控件。

本轮将章节阅读与数据探索分开。仅修改本地代码，没有提交、推送或部署；其他进行中的章节改造、依赖更新及 skill 安装不属于本轮新增内容。

## 阅读与探索的职责

- 章节保留原问题、正文、代表图与旧深链接。不再用“选择本章分析”下拉框反复覆盖正文。
- “探索数据 · 本章数据专题”展示可搜索的卡片。RW/OA 复选框只筛选目录，不修改章节 URL、正文、主图或来源说明。
- 可用卡片稳定排序在前；缺少所需来源的卡片保留在后，以次要颜色标记且没有可点击 href。至少保留一个来源。
- 可用卡片是原生链接，使用 `target="_blank"` 和 `rel="noopener noreferrer"`。普通点击、键盘激活、复制链接或浏览器新标签操作均可使用，原章节不导航。
- 目录筛选是当前章节的临时探索状态；刷新后从章节 URL 的 `sources` 重新初始化。复制专题链接保留专题的来源和切片，而不是临时搜索词。

## 路由契约

```text
章节：      #/snapshot/{section}?sources=rw%2Coa
旧精确链接：#/snapshot/{section}?sources=rw%2Coa&slice={chart}/{slice}
专题：      #/snapshot/{section}/topic/{topic}?sources=rw%2Coa
专题切片：  #/snapshot/{section}/topic/{topic}?sources=rw%2Coa&slice={chart}/{slice}
学科树：    #/snapshot/fields/topic/discipline?sources=oa&taxonomy=concepts&population=A1&node=…&parent=…&metric=rate
```

例：`#/snapshot/time/topic/annual-counts?sources=rw`。

`routes.js` 同时解析旧链接与新专题路径；仍使用原来源解析和聚合校验。未知专题、错误路径、跨专题切片或不兼容来源显式报错，不悄悄替换结果。非学科专题不接受学科树参数。学科树专题中的节点、父级、分类和指标链接始终留在专题路径。

## 专题组织与图表

当前 109 个已发布切片归入 44 个分析专题，另有完整两层学科树入口，共 45 张卡片：概览 3、时间 5、学科 7、原因 4、地理 4、机构作者 6、出版 6、引用 4、质量 6。

通常按现有分析 ID 归入同一专题，不合并不同统计值。国家计数与发文基数比率拆开；月度控制图与原期刊月份矩阵拆开。Subject、Topics、Concepts 不混成一个分类。

专题图上提供两个明确维度：

1. **研究总体单选**：OA 标记论文、RW 原论文或 RW × OA 匹配子集按真实依赖标注，不把匹配数据标成 RW 单库。
2. **统计范围与方法单选**：层级、机构/署名国家、期刊/出版集团、文献类型和随访窗口等保留各自已发布切片。

切换总体时只匹配同一切片范围；当前范围在另一总体不存在时禁用该选项，不自动变成其他方法。标题、发现、图、单位、n/N、方法、日期和导出由同一活动切片提供；切换写入专题 URL，刷新和后退可恢复。调整“专题可用来源”后若当前切片失去依赖，会显示不可用，等待读者重新选择。

**代表性合图：RW 发表年与撤稿年。**

- 直接叠加 `T1/B-published` 和 `T1/B-retracted`，实线/虚线加颜色区分，使用同一纵轴和计数单位。
- 两条线是同一研究范围的不同年份分组，不相加，也不把同年两条线相除当作撤稿率。
- 仅在两份切片均 ready、同 release、同观察截止且单位为篇时叠加。
- 悬停、聚焦或点击点显示同年的两种计数；Enter 锁定、Esc 取消，左右键切换数据点。序列复选框同步显示对应观察句，至少保留一条。
- 缺失年份不补零、不跨缺口连线，未完整年度用空心点。隐藏序列不重标纵轴、不修改完整表和原 CSV。
- 保留两条原序列的完整数据表、各自的 CSV 和逐单元证据。没有创建并集或新的公开聚合。

其他专题保留原图形语义，通过研究总体/范围切换共用一张图；没有强行叠加不可比的区间、矩阵、累计分布或比例。

## 视觉取舍

延续已验收报告的中文字体与浅色 token：背景 `#fffefb`、正文 `#20313d`、次要文字 `#52616c`、交互强调 `#176b73`、分隔线 `#d9dedf`；对比图第二序列用 `#a45125`，并用虚线确保不只靠颜色区分。

比较“章节原位切换”和“章节卡片 → 独立专题”两种结构后，按本轮要求选后者。卡片只承载研究问题、来源和可用视图数量，不复制整张图或制造卡片套卡片。桌面三列、平板两列、手机一列。保留已有固定章节目录，不新增第二个全站目录。研究叙事仍由 research-report-design 约束；实施期间新增的 frontend-design skill 已读取并用于最终视觉核对，没有因此迁移技术栈或安装依赖。

## 变更文件

- `src/report/topics.js`、`routes.js`：目录分组、稳定链接、来源可用性与解析。
- `src/report/TopicIndex.jsx`、`TopicReport.jsx`、`topics.css`：卡片目录和独立专题交互。
- `src/report/AnnualComparison.jsx`：RW 两种年份同图及对应解释、表格、导出。
- `src/report/ChapterReport.jsx`、`OverviewReport.jsx`、`ReportChrome.jsx`、`SnapshotReport.jsx`：接入新索引与专题分支。
- `src/report/DisciplineExplorer.jsx`：注入专题节点 href，默认旧链接不变。
- `src/report/overview.css`：将原通用 input 的复选框尺寸规则限制到 checkbox，避免搜索框被缩成小方框。
- `tests/snapshot-topics.test.mjs`、`scripts/check-topics-browser.mjs`：新增数据/路由和浏览器回归。
- 原概览、章节浏览器脚本：旧切片/来源 URL 的回归继续保留；不再操作已移除的下拉框，卡片交互由新脚本验证。

## 实际检查与截图

本轮基于本地 checkout 检查，数据 release 仍为 `oa-2026-06-26-0d8f97ed1bf5`。没有核对线上部署版本。

| 检查 | 结果 |
| --- | --- |
| `node --test tests/snapshot-*.test.mjs` | 38 项通过，其中新增 4 项专题测试 |
| `npm test` | 51 项 Python 测试通过 |
| `npm run build` | 通过，公开数据门槛通过 |
| 专题浏览器脚本 | 26 组通过；9 章卡片筛选、排序、搜索、新标签；109 个专题切片的逐行 CSV；109 个旧链接 |
| 章节浏览器脚本 | 44 组通过，106 个旧章节 CSV 核对通过 |
| 概览浏览器脚本 | 11 组通过，包括键盘/触摸、200% 字号和原精确导出 |
| 三种尺寸 + axe | 1440×900、768×1024、390×844；目录、双序列图、总体切换页面通过，无整页横向溢出 |
| 数据契约 | public/data、pipeline、schema、sources、discipline 计算逻辑无改动；公开数据仍 1,895,280 字节 |

本地证据目录 `/tmp/sro-topic-review/`：

- `before-index.png`：改造前的章节下拉选择器。
- `review/`：第一轮截图和检查结果；发现搜索框尺寸继承问题及面包屑链接缺少非颜色区分。
- `after/index-{desktop,tablet,mobile}.png`：确认后的目录；同目录 `annual-*` 为双序列专题，`dataset-*` 为总体单选专题。各有 `-full.png` 全页版本。
- `after/checks.json`、`chapters/checks.json`、`overview/checks.json`：最终机器检查结果。
- `node-tests.log`、`python-tests.log`、`build.log`：命令输出。

截图已实际打开审查；先集中修复，再确认一次，没有继续循环视觉润色。原构建仍提示旧主入口大于 500 kB；Firefox、Safari、人工屏幕阅读器和线上部署未检查。临时截图不会随网站发布，清理 `/tmp` 会删除证据。

浏览器复跑：

```bash
PLAYWRIGHT_MODULE=/tmp/snapshot-browser-check/node_modules/playwright/index.mjs \
CHROMIUM_PATH=/home/ider/.cache/ms-playwright/chromium-1169/chrome-linux/chrome \
AXE_PATH=/tmp/snapshot-browser-check/node_modules/axe-core/axe.min.js \
REPORT_QA_OUT=/tmp/sro-topic-review/after \
node scripts/check-topics-browser.mjs
```
