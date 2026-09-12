# Topics 四层分类树与逐年统计

## 本轮范围

按用户确认的方案，把 Topics 的 Field → Subfield 两层入口扩展为：

```text
Domain 大领域（4）
  → Field 学科（26）
    → Subfield 子学科（252）
      → Topic 具体研究主题（4516）
```

数字来自本次固定快照的实际分类目录，不宣称所有 OpenAlex 版本都具有相同节点数。另保留每层的标签缺失组；它们不是额外的学科或大领域。四个 Domain 是 Life Sciences、Social Sciences、Physical Sciences、Health Sciences，而不是四个 Topic。

Subject 与 Concepts 仍为各自原有两层体系，不建立人为对应关系。原 Field/Subfield 节点 ID、数据、链接继续有效；默认根入口由“全部主学科”改为“全部大领域”。此前缺失子学科的父级导航参数保留兼容处理。

## 统计方法和实际补算

旧缓存只有 Field/Subfield 的同口径年度分母。因此本轮实际运行 `pipeline.snapshot_taxonomy`，对 2446 个已验证 works 分片补算 Domain 与 Topic，同时复核 Field/Subfield 和 Concepts；没有拿父级分母、any-topic 多标签计数或目录 `works_count` 代替末级分母。

- 执行：8 个 worker × 每 worker 4 个 DuckDB 线程，内存上限每 worker 16 GB；本次扫描耗时约 278 秒。
- 隔离目录：`data/processed/topic-hierarchy-20260912`，旧来源 run 与缓存通过只读用途的路径引用复用，新 taxonomy 缓存和报告写入隔离目录，不覆盖原 run 的扫描结果。
- 新扫描配置：`taxonomy-cohorts-v2`；每个缓存分片绑定来源指纹与内容 SHA-256，报告生成前重新验证。
- 本地聚合版本：`oa-2026-06-26-7c6e5f2b98d6`；OA 截止 `2026-06-26`，RW 文件截止 `2026-09-10`。

按主主题 `primary_topic` 归类，每篇论文每层只计一次。每个节点独立保留逐年 n、N；四层的分子/分母汇总均复现总体，各父节点的直属子节点汇总也与父节点逐年完全一致。

`A1` 沿用通过主体库、article、原论文身份与日期筛选的 OA 撤稿标记论文。`C_D` 沿用截至 OA 截止日前已由 RW 记录撤稿、匹配并通过相同筛选的原论文，不是全部 RW，也不是两库之和。论文分类与发表年份均使用同一 OA 快照字段。

每个节点、发表年的比例为 `n / 同节点同年合格发表论文 N × 100%`；另保留数量、样本内覆盖和每万篇指标。时间轴是原论文发表年，不是撤稿事件年。年度范围为 2000–2026，全历史首项保留更早记录；近期队列观察期较短，末年不完整。N=0 的比例未定义，不显示为观测零；小基数仍按原门槛限制排名。

## 页面设计

继续复用现有研究出版物的字号、色彩、Figure 和方法分层。比较“首屏展开数千节点”和“按需展开四层索引”后采用后者：阅读正文先看研究范围和大领域分布，分类索引在原次级区域展开。

- `TopicTree` 使用原生 details/summary，初始仅显示大领域；打开分支才渲染下一级，不一次创建 4516 个 Topic 链接。
- 搜索覆盖全部层级的名称和 ID；分批展示搜索结果只影响界面，不裁剪索引数据或统计分母。
- 面包屑展示完整的 Domain → Field → Subfield → Topic 路径。
- 非末级节点展示直属下一层的分布；末级 Topic 展示同一 Subfield 下的主题对照，并显示该 Topic 的年度趋势。
- 弹层保留独立选择状态、独立页链接、键盘关闭与焦点恢复。所有旧的 109 个平铺分析入口继续保留。

可用示例：

```text
#/snapshot/topics?sources=oa
#/snapshot/topics?sources=oa&node=https%3A%2F%2Fopenalex.org%2FT10001&metric=proportion
#/snapshot/topics/topic/discipline?sources=rw%2Coa&node=https%3A%2F%2Fopenalex.org%2FT10001&population=C_D&metric=proportion
```

## 数据格式与预算

4516 个 Topic 的完整年度数据不能继续逐字展开在 2 MiB 静态数据预算内。本轮新增可逆的 `zlib-json-v1` 聚合编码，使用 Python 标准 zlib 与固定版本的 [fflate](https://github.com/101arrowz/fflate) 0.8.3 解码，不迁移 React 或图形库。依赖安装使用 `--ignore-scripts`，不安装额外 hook。

大型 `discipline_explorer` 和部分大表的 `row_values` 使用 `{encoding, bytes, sha256, data}` 封装；data 是 zlib 内容的 Base64。原文件哈希先校验，解压输出限制为 8 MiB，并复核实际长度和解压后 SHA-256，再进行完整统计结构与禁用原始字段检查。CSV 仍导出解码后的原始精度聚合行，不导出编码载荷。

新消费者应通过 `decodeExplorer` / `decodeChartRows` 或 `validateChunk` 读取数据，不能把压缩封装当成节点数组。前端解码器与此数据版本需一起交付，旧客户端会拒绝新编码而不是显示替代数值。表格数值在压缩前沿用原有六位小数规则。

本地 `public` 与 `dist` 统计资产均为 **2,010,929 bytes**，小于 2 MiB，仍只有聚合统计和原 36 个展示样本。将新旧数据都解码后，逐一对照全部 109 个旧图表的完整契约、国家数组和原有分类节点的 n/N：除 release ID 与原有非确定性数组顺序外，旧图表一致，原统计数值全部一致。

## 检查和截图证据

基线为本地 `767ed56` 上已有未提交工作树，而非部署站点。初审截图 `/tmp/sro-topic-hierarchy-review/before/` 显示旧树从 Field 起，没有 Domain 和具体 Topic。已实际查看桌面和手机初审截图。

本地浏览器检查使用独立预览 `http://127.0.0.1:4186/`、Chromium 136.0.7103.25、已有 Playwright 库及 axe。没有声称安装或调用缺失的浏览器 skill。

- `node --test tests/snapshot-*.test.mjs`：51 项通过，包括 4516 个 Topic 的两总体逐年分母、完整祖先链、旧链接、分区校验和压缩损坏/超长解压拒绝。
- `npm test`：54 项 Python 测试通过。
- `npm run build`：构建与 public/dist 数据校验通过。
- `scripts/check-topic-hierarchy-browser.mjs`：检查完整下钻、搜索、四层两总体四指标的 32 份年度 CSV、刷新、旧链接、来源限制、弹层与三个视口。
- `scripts/check-topics-browser.mjs`：回归 109 个专题切片 CSV 与 109 个旧链接。
- `scripts/check-cohort-browser.mjs`：回归学科和国家的比例与年度指标。

浏览器结果、截图和日志位于 `/tmp/sro-topic-hierarchy-review/`；最终状态以对应 `checks.json` 为准。视口为 1440×900、768×1024、390×844。

## 限制与环境问题

首次浏览器尝试遇到预览端口拒绝连接；定位为 Vite 遍历新分析缓存的符号链接，耗尽文件监听配额。已在 `vite.config.js` 排除原本就被 Git 忽略的 `data/raw`、`data/cache`、`data/processed`，不修改系统监听限额，也不把原始数据加入站点。随后使用独立端口重新检查。

只验证本地 Chromium，未验证线上站点、Firefox 或 Safari。此前国家维度缓存完整性审查指出的缺口不是本轮 Topics 改造的修复范围。既有 RW 入口 bundle 大于 500 kB 的构建提示仍在；近期队列偏差、回溯验证的传输证据缺口及 Concepts 的旧分类限制均保留。

本轮未提交、推送或部署。
