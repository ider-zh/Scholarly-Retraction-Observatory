# RW 原始署名与 OpenAlex 作者身份排行

## 范围与设计

本次为本地统计与展示扩展，不提交、推送或部署。审查基线 HEAD `767ed56`，工作树包含此前其他修改，不将其归入本次实现。

实际截图审查本地 `http://127.0.0.1:4187/#/snapshot/entities/topic/author-top?sources=rw%2Coa`：旧标题为“作者关联论文数 Top 20”，正文已有 OA 身份列，但没有 RW 原始署名专题；读者可能将第一版姓名字符串合计误认成个人数量。

选择两个独立专题入口，而不是把两种不同聚合对象放进同一个排行切换。复用原 Figure、图注、表格和弹层，保留现有颜色与中文文字层级。OA 专题内部仍可单选 OA 标记论文或 RW 匹配论文；这两者都按 OA 作者 ID 统计。

## 数据契约

- 新增 `rw-author-names/B-raw-author-names-top-20`：RW 原始署名字符串、全计数、前 20 项；总体为当前快照去重后的全部 RW 原论文 66,700 篇，不要求 OA 匹配，不施加 OA article 筛选。
- 原始 CSV 的 SHA-256 必须与扫描 provenance 中的 `rw_csv_sha256` 一致。仅连接既有 canonical 原论文的 `rw_ids`，不重新定义原论文队列。未连接的空行或其他通知类别不会加入姓名统计。
- 以分号拆分 Author，去首尾空白；同一原论文多条记录中的相同字符串只计一次，跨论文按精确字符串累计。不统一大小写、拼写、姓名顺序，也不推断身份。
- 精确缺失规则：空值以及忽略大小写后的 `unknown`、`unavailable`、`not available`、`n/a`、`na`、`none`、`null` 不进入排行。已知与缺失并存另计覆盖，不把其余署名丢弃。
- 当前有非占位署名 66,587 篇，无非占位署名 113 篇，同时含已知署名与缺失记录 0 篇；180,410 个不同姓名字符串不是独立作者人数。关联次数 274,366，不是不同论文总数。
- 本次 RW 姓名字符串 `Wei Wang` 168 篇、`Wei Zhang` 167 篇。第一版 RW 截止 2026-09-09，本次为 2026-09-10；不硬编码旧版 166，也不混用旧快照分母。
- 既有 `author-top/A1-author-top-20`、`author-top/C-author-top-20` 保持 OA ID、计数、排序、筛选及截止日期规则。OA ID 消歧仍可能拆分或合并身份。这不是责任排行，也不能与 RW 字符串排行直接比较个人名次。
- 缺少 `--rw-csv` 时，新专题标记 `not_computed`，不填零或借用旧版数据。输入哈希、重复的已关联 Record ID、缺失连接不通过则停止生成。
- 新源码哈希与是否提供 RW 作者来源进入报告版本计算。浏览器校验新排行的来源哈希、覆盖分区、整数 n/N、排名、Top N、单位和排除占位值。
- 第一版 `public/data/report.json` 不修改；不公开逐篇名单、原始 CSV、匹配记录或作者网络。

## 路由与复现

- RW：`#/snapshot/entities/topic/rw-author-names?sources=rw`
- OA：`#/snapshot/entities/topic/author-top?sources=oa`
- 匹配子集旧链接继续有效：`#/snapshot/entities?sources=rw%2Coa&slice=author-top%2FC-author-top-20`
- 联合选择下两个专题独立存在；只选 RW 时 OA 入口禁用后置，只选 OA 时 RW 入口禁用后置。卡片打开弹层，不替换章节内容。表格、方法与 CSV 保持绑定当前选择。

```sh
python -m pipeline.snapshot_report data/processed/topic-hierarchy-20260912 \
  --output-dir data/processed/author-ranking-20260912/report \
  --rw-csv /mnt/hg02/openalex-snapshot/analysis/rw/retraction_watch.csv
python -m pipeline.publish_snapshot data/processed/author-ranking-20260912/report
python -m unittest discover -s tests -p test_author_names.py
node --test tests/snapshot-*.test.mjs
npm test
npm run build
```

`publish_snapshot` 只原子替换本地 public 聚合目录，不是远程部署。完整性与 payload 门槛不变；原始快照与源扫描分片只读，报告写入独立忽略目录。

## 浏览器与验收记录

实际浏览器脚本：`scripts/check-author-rankings-browser.mjs`。使用本机既有 Playwright/Chromium 与 axe，不安装新依赖或 hook。运行时设置 `PLAYWRIGHT_MODULE`、`CHROMIUM_PATH`、`AXE_PATH` 与 `REPORT_QA_URL`。

前截图：`/tmp/sro-author-ranking-review/before-desktop.png`、`before-mobile.png`。后截图与浏览器结果保存于 `/tmp/sro-author-ranking-review/after/`，覆盖 1440×900、768×1024、390×844，分别查看 RW 与 OA、口径单选、旧深链接、弹层、CSV 和 WCAG。测试结果以该目录 `checks.json` 为准；前截图为本地 checkout，不是部署站点。

实际完成结果：

- 本地版本 `oa-2026-06-26-1f41fe8f2476`；新增后共 110 项切片。旧版 109 项逐项比较解码后的完整图表契约，仅忽略 release ID 与数组顺序，全部不变；含两张 OA 作者排行。证据 `/tmp/sro-author-ranking-review/contract-check.json`。
- Python 59 项通过，其中新增姓名计数测试 5 项；Node 58 项通过，含来源隔离、异常来源与覆盖拒绝、全部切片路由及原有数据测试。新增切片后对应总数断言由 109/106 更新为 110/107。
- `npm run build` 通过；public 与 dist 聚合总量均 2,016,328 字节，低于 2 MiB，展示样本仍为 36。保留既有大 chunk 提示，没有为此次表格迁移技术栈。
- 浏览器 8 组检查全部通过：RW/OA/联合入口、RW 精确 CSV、两种 OA 总体切换及精确 CSV、旧链接重载与来源不足拒绝、弹层隔离、三种尺寸 WCAG/无页面横向溢出、无未捕获错误。
- 一次确认复跑同样 8/8 通过；结果在 `/tmp/sro-author-ranking-review/confirmation/checks.json`，没有继续循环视觉微调。
- 已实际查看前桌面截图，以及后桌面 OA 表格、平板 RW 表格、手机 RW 表格截图；不是仅凭截图文件存在推断视觉结果。完整 20 行置于现有可键盘滚动表格容器，完整聚合表与导出仍可用。
- 原始 CSV 含未纳入 canonical 队列的重复空 Record ID 行。初次生成在严格重复校验处停止、未替换 public；修正为先按已纳入的 canonical `rw_ids` 连接，再校验重复与缺失。合成测试保留重复空行和重复已连接 ID 两种情况；前者忽略，后者拒绝。

不执行两位同名字符串的逐篇身份审计：当前统计仍不能说明这些字符串对应几位真实作者。其他章节已有问题不在本次范围内。

## 后续：仅补充同名现象说明

按用户要求，将已观察到的“RW 同一姓名字符串汇总、OpenAlex 按不同作者 ID 区分”写入两个作者排行的表格前，并同步机构与作者章节的阅读指南。共用 `AuthorIdentityNote.jsx`，RW、OA、匹配子集及专题弹层均使用同一说明。

这是一项对照观察的文字记录，不是新增逐篇作者身份审计。没有给出未经验证的“某姓名对应几位真人”或具体 ID 映射；明确保留 OA 可能误合并/误拆分、两份排行范围与匹配覆盖不同、不能直接比较个人数量/名次的限制。

本次不运行数据生成、清洗、匹配或作者消歧，不修改计数、排序、原始姓名、作者 ID 或 CSV。公开聚合与 pipeline 文件以本轮修改前后的 SHA-256 核对。只补充说明组件、引用和浏览器断言；截图和检查输出保存在 `/tmp/sro-author-note-review/`，原始排行截图为 `before.png`。未提交、推送或部署。

本轮确认：58 项 Node 测试、生产构建、8 组作者排行浏览器回归全部通过；公开聚合和 pipeline 的前后 SHA-256 全部一致。浏览器覆盖两份排行、OA 两种总体、旧链接、弹层、精确 CSV 和三种尺寸 WCAG 检查。说明截图为 `after/{desktop,tablet,mobile}-note.png`，已实际查看桌面与手机说明；没有为此改变视觉布局或统计。保留原有大包构建提示。

手机元素截图受视口裁剪，另保存并查看了 `after/mobile-full.png`，确认三段说明随页面滚动完整呈现，不将局部截图的空白误认为正文丢失。
