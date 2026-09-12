# 阅读入口与专题弹层

## 范围与设计依据

本轮仅更新报告的阅读说明和展示交互，不提交、推送或部署。基线为本地 `767ed56` 加已有未提交工作树，不代表部署站点。检查地址 `http://127.0.0.1:4173/#/snapshot/overview?sources=rw%2Coa`。

已读取项目 `AGENTS.md`、`frontend-design`、`research-report-design`、现有设计和统计规范。复用 React、现有图形与浏览器原生 `dialog`，没有引入 Tailwind、另一个图表框架或未知 hook。未安装的 Impeccable / Playwright skill 没有被调用；实际浏览器检查使用已有 Playwright 库、Chromium 136.0.7103.25 和 axe。

截图审查发现：概览用记录筛选的技术结论作为研究入口；方法和目录之间存在无内容的双线间隔；目录仍折叠且在章节方法之前；正文没有复用专题聚合图与口径控件。

两个低成本方案：

```text
A（采用）                        B（不采用）
侧栏 | 研究说明与来源             侧栏 | 正文 | 常驻专题面板
     | 正文图表及本图口径              | 图表 | 同时显示筛选与另一图
     | 方法与限制
     | 展开的专题目录 → 弹层
     | 继续阅读
```

B 会挤压图表且同时呈现多套上下文。A 保持单条阅读路径，用户主动打开专题才进入次级探索。

沿用纸面 `#fffefb`、正文 `#20313d`、次级文字 `#52616c`、细线 `#d9dedf` 和数据强调 `#176b73`。中文系统字体，正文左对齐；桌面保留侧栏，紧凑屏保留章节抽屉。弹层桌面最大 1120px，移动端全屏，关闭按钮固定在弹层顶部。

## 实现与链接契约

- 概览开场先解释撤稿、研究问题、RW 与 OpenAlex 的用途；原有 114,538、50,331、43.94% 等筛选数据保留为图旁范围说明，不再冒充全站研究结论。
- 每章目录默认展开，置于章节方法之后、“继续阅读”之前。移除相邻方法与目录间的重复顶部边线。
- `TopicAnalysis` 供正文、弹层、独立专题共用：同方法的研究总体单选、统计范围单选，以及 RW 发表年/撤稿年双序列。单一视图不显示无用的单选框。
- 正文口径切换更新原章节 `slice`，图、观察、单位、限制、原始表、CSV 同步；支持刷新与浏览器历史，不变成专题 URL。
- 卡片普通点击和键盘激活打开 `TopicDialog`，不改变原章节 URL、图表、来源、搜索或阅读位置。弹层没有章节导航、开场介绍和重复研究问题标题。
- 弹层使用原生模态背景、Escape、关闭按钮、遮罩点击、Tab 边界循环、关闭后的触发卡片焦点恢复和背景滚动锁定。
- 卡片 href 保留；浏览器复制链接、修饰键新标签操作仍可使用。弹层底部的独立页面链接携带当前专题、来源、切片或学科路径。弹层选择是临时状态，关闭后不写入原章节历史。
- 每个图表实例的 radio 名称独立，避免弹层选项取消正文的选中状态。
- 学科入口有 OA 且未指定旧路径时默认 Concepts；RW-only 使用 Subjects。显式 Topics / Concepts / Subjects 深链接和已有节点继续按原参数解析，不自动改换分类树。
- “所有主题，多标签”两个选项改为明确的“按学科汇总”和“按主题汇总”，只改控件标签。

## 保留的数据契约

发布版本 `oa-2026-06-26-0d8f97ed1bf5`；OA 截至 2026-06-26，RW 截至 2026-09-10。

没有修改公开聚合、manifest、流水线、`sources.js`、`discipline.js` 或统计分母。联合选择不是去重并集，不将 RW 和 OA 相加；不把缺失、未计算或不可用变成零。Concepts 的旧标签、历史父级、多父级重叠及覆盖限制仍可见。

公开数据检查仍为 1,895,280 bytes、36 个展示样本，109 个分析切片。

## 实际检查与截图

基线：`/tmp/sro-reading-update/before/desktop.png`、`mobile.png`（本地完整页面）。

初审：`/tmp/sro-reading-update/review/`。集中修正单选框移动端换行、重复选项名称和无用的单选框；随后一次确认，未无限循环润色。

- `node --test tests/snapshot-*.test.mjs`：39 项。
- `npm test`：51 项 Python 测试。
- `npm run build`：构建与公开数据检查。
- `scripts/check-overview-browser.mjs`：11 组；RW/OA/联合、三种尺寸、筛选精确值与导出、旧链接、复制、键盘、200% 字号及 axe。
- `scripts/check-topics-browser.mjs`：26 组；109 个专题切片精确 CSV、109 个旧章节深链接、独立目录、来源限制、无效路径、专题历史、双序列交互、三尺寸 axe。
- `scripts/check-chapters-browser.mjs`：44 组；8 章 × 三尺寸、106 个非概览切片精确 CSV、三体系与节点、地理口径、旧链接。
- `scripts/check-sidebar-browser.mjs`：7 组；侧栏/抽屉、键盘、触摸、章节跳转和 axe。
- `scripts/check-reading-browser.mjs`：15 组；全部 45 个卡片弹层、20 组正文数据集切换、刷新和历史、弹层与正文互不覆盖、关闭和焦点返回、Concepts 默认及旧 Topics 链接。

最终确认输出：`/tmp/sro-reading-update/final/checks.json`；1440×900、768×1024、390×844 各有 `*-overview.png`、`*-overview-full.png`、`*-annual-body.png`、`*-annual-dialog.png`、`*-dataset-dialog.png`。其他检查结果分别在同目录下的 `overview/`、`topics/`、`chapters/`、`sidebar/`。

## 限制

未验证部署站点，也未覆盖 Safari / Firefox。移动端长方法、表格和大量专题仍需滚动，完整数据表保留横向滚动；不为了缩短页面删除证据。原 RW 入口的构建包超过 500 kB 的既有提示仍存在。没有为了样式迁移到 Tailwind。
