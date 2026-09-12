# 报告侧边导航调整

## 目标与设计

本轮实际读取并使用 frontend-design（主要视觉方向）与 research-report-design（研究内容与数据边界）。用户指出全站章节目录与专题面包屑上下堆叠；本轮只改变导航外层，不改变研究发现、数据或分析方法。

本地审查地址：`http://127.0.0.1:4173/#/snapshot/overview/topic/screening?sources=rw%2Coa`。没有检查部署站点；截图不代表线上版本。数据仍为 `oa-2026-06-26-0d8f97ed1bf5`。

采用完整文字侧栏，而不是只显示图标的窄栏：研究概览、时间、学科等名称对零上下文读者更明确。桌面保留常驻目录，窄屏用抽屉，避免把正文压缩成狭窄列。

```text
桌面（≥1024 px）                 平板 / 手机
左侧目录 │ 正文面包屑             简短站名        报告目录按钮
站名     │ 研究问题               正文面包屑
章节列表 │ 发现、主图             研究问题、发现、主图
原版入口 │ 方法与专题入口         打开按钮 → 左侧目录抽屉
```

- 桌面侧栏宽 248 px，独立滚动；正文预留同等宽度，不与目录重叠。顶部不再重复排列章节链接。
- 活动章节用边线、背景与字重同时标记。专题页仍高亮所属章节；正文面包屑负责表达“章节 / 专题 / 当前分析”。
- 平板和手机仅保留紧凑站名与“报告目录”按钮。抽屉打开时以原生 dialog 隔离背景，支持关闭按钮、Esc、点击遮罩和章节导航后自动关闭。
- Tab / Shift+Tab 在抽屉内循环；关闭后焦点回到入口。跨断点切换时关闭抽屉，解除滚动锁定。
- 字体沿用现有中文系统字体，正文 17/16 px，侧栏名称 15 px，站名 18 px。正文纸色 `#fffefb`，侧栏 `#f3f6f5`，文字 `#20313d`，次要文字 `#52616c`，活动强调 `#176b73`，边线 `#d9dedf`。
- 保留全部九章、原 RW 报告入口、sources 与专题深链接；不增加分析筛选器或改变卡片行为。

## 变更范围

- `src/report/ReportChrome.jsx`：共用侧栏、窄屏抽屉与焦点行为，覆盖概览、章节和独立专题。
- `src/report/navigation.css`：新导航布局、状态和断点；无需新增依赖。
- `src/report/overview.css`：移除旧顶部目录样式，按紧凑顶栏重设滚动定位间距。
- `scripts/check-sidebar-browser.mjs`：响应式、焦点循环、键盘/触摸、来源链接与章节导航检查。
- `scripts/check-overview-browser.mjs`：将旧“手机始终展示全部顶部链接”的断言改为抽屉交互；其他概览验证保留。

## 检查与证据

本地截图目录：`/tmp/sro-sidebar-review/`。

- 改造前：`before-desktop.png`、`before-mobile.png`。
- 首轮审查：`review/desktop-topic.png`、`review/tablet-topic.png`、`review/tablet-drawer.png` 等。
- 修复后：`after/desktop-topic.png`、`after/tablet-topic.png`、`after/mobile-topic.png` 与两种窄屏的 `*-drawer.png`。
- 最终机器确认：`confirmation/checks.json`；同目录保存三个尺寸与抽屉截图。
- 概览和专题回归：`overview/checks.json`、`topics/checks.json`。

实际打开审查了改造前桌面、改造后桌面、平板抽屉和手机正文/抽屉。集中修复了键盘焦点循环；测试另等待原生 close 事件更新 React 的 `aria-expanded`，避免用同步断言误判异步关闭状态。没有循环更换视觉方案。

检查命令为 `node --test tests/snapshot-*.test.mjs`、`npm test`、`npm run build`、`git diff --check`，以及现有 Playwright/Chromium 的侧栏、概览和专题浏览器脚本。38 项 Node 与 51 项 Python 测试、生产构建通过，数据门槛仍为 1,895,280 字节。浏览器实际测试 1440×900、768×1024、390×844，并运行 axe WCAG 2/2.1 A/AA 自动规则。

最终结果：侧栏 7 组、概览 11 组、专题 26 组浏览器检查均通过；109 份专题 CSV 与 109 个旧深链接核对通过，无页面脚本错误。

原有主入口大于 500 kB 的构建提示仍在；未做 Firefox、Safari 或人工屏幕阅读器认证。本轮未提交、推送或部署，临时截图不会自动上传到网站。
