# OpenAlex Concepts / Topics NGD 数据层 Spec

版本：`taxonomy-ngd-spec-v1`。状态：研究决策 Q1–Q15 已确认；工程实现与全量验收已完成，证据见 `COMPLETION.md`。
本规范记录本次访谈的最终约定，覆盖原提案中的含糊层级、单父级字段及异常处理。

## 1. 目标与边界

按学科 Work 集合计算完整 L1 × L0 矩阵，保存原始计数、NGD、排名、数学切片，
以及逐 Work 二值 membership 缓存，支持后续交叉分析和重算共现指标。

不计算单篇距离后求平均；不用 score、embedding 或引用权重。
本阶段不计算 L0 × L0、L1 × L1、其他层级、年度矩阵、撤稿率、回归或因果关系。
不改变现有报告的 primary-only 方法，不扫描引用网络，不重算 Disruption。

## 2. 独立性与输入来源

模块目录为 `taxonomy_ngd/`；不得在导入时启动计算，不绑定网站 build 或现有生产作业。
输入为冻结的 `/mnt/hg02/openalex-snapshot/data/parquet` 及其验证清单。
必须验证实际 manifest、输入文件身份、schema、Work 主键与分类实体完整性。
快照版本来自来源证据，不得使用下载时间或生成时间替代。

只读检查发现当前输入具有 19 个 Concept L0、284 个 Concept L1、4 个 domains、
26 个 fields、252 个 subfields、4,516 个 topics。正式执行必须重新核实并记录。
此前验证的全库规模 510,372,821 Works 仅作为核对参考，不能代替本次输入身份核查。
继承已接受的回溯验证政策及历史下载前证据缺口，不补造 provenance。

现有 Disruption 基础缓存仅有 primary topic 信息，不能替代本任务的完整多标签输入。
任何旧缓存只有在来源哈希、覆盖、列和规则均符合本规范时才可复用。

## 3. 统一 Work universe

`N = count(distinct canonical_work_id)`，纳入完整 core + xpac。
身份有效指合法 OpenAlex Work ID，统一为 `https://openalex.org/W<正整数>`。
不得按撤稿状态、发表年、日期、类型、引用数、文献角色、学科或标签存在与否筛选。
缺 DOI、年份、语言或学科不删除 Work；两套矩阵必须使用同一 N。

重复或冲突的 Work 身份属于结构异常，不允许任意取第一条或合并标签后静默继续发布。
空 universe 阻止正式发布。无标签 Work 仍在 N 中，但不贡献该体系的 membership。
分别记录各体系有标签、有 L0、有 L1、两层均有标签的覆盖率，不以覆盖数替换主结果 N。
后续若定义新子总体，必须生成新分析版本及新 N，不能混入本次主矩阵。

## 4. 分类实体与 membership

### 4.1 Concepts

- 分析 L0/L1 为实体表的原生 `level=0/1`。
- 使用 `work.concepts[]` 全部附带 ID，包含零分和低分标签，不另设 score 阈值。
- ID 在快照 Concept 实体表中解析；level/name 以实体表为准，内嵌信息用于审计。
- 只选本任务两层，其他合法层级忽略但不视为坏标签；不新增祖先标签。
- 同一 Work 对同一 ID 仅计一次；缺失列表和空列表均不贡献 membership，但保留不同源状态。

### 4.2 Topics

真实层级是 domain → field → subfield → topic。本模块分析 L0=field、L1=subfield，
不声称它们是 OpenAlex 原生 level 0/1；domain 不属于本次矩阵。

使用 `work.topics[]` 中全部已附带 topic ID，不只用 `primary_topic`，不另设阈值。
从同一快照的 topic 实体映射到 subfield，再映射到 field；实体间链必须一致。
分别对 Work 的 field 集合和 subfield 集合去重，再计算跨集合的所有 pair。
不能只计每个 topic 自己的父子 pair：同一 Work 的不同 topics 也会产生跨 field 共现。
空 topics 不以 primary_topic 回填。Work 内嵌链与实体链冲突须审计并阻止正式发布。

### 4.3 异常

无标签属于正常缺失。非法 ID、悬空实体、映射冲突、taxonomy 主键冲突、身份冲突
属于结构异常：保留原始证据和受影响 Work，扫描/checkpoint 可以继续，但正式发布阻断。
不得猜名称、静默删标签、删 Work 或切换来源来绕过失败；处理例外需显式版本化新规则。

## 5. 父级关系

本快照 Concepts 的两层 `ancestors` 为空，不能据此声称没有父级。
批准复用 `data/reference/openalex-concept-tree-v3.json` 的历史官方 V3 分类器映射，
并验证它与源对象哈希、当前节点 ID 的对应关系。来源说明见
`docs/OPENALEX_DISCIPLINE_EXPLORER.md` 与 `pipeline/concept_tree_reference.py`。
本地冻结映射含 284 个 L1、361 条 L0 连接，77 个 L1 有多个父级；正式执行需核验。
这不是当前快照原生父级，只用于标记和排名排除，绝不修改 membership 或 NGD。

Topics 父级来自当前 subfield → field 实体映射。
输出 `parent_l0_ids: list<string>` 和同序 `parent_l0_names: list<string>`，按 ID 稳定排序。
它们替代原提案的单值 `parent_l0_id/name`，不得强选一个主父级或将 pair 按父级重复展开。
另存一条关系一行的 `taxonomy_parent_edges.parquet`，保留体系、两端 ID/name、关系来源版本。
已知 L1 缺少应有关系是结构异常；不能把“关系未知”当作“不是父级”。

`is_parent_pair = l0_id in parent_l0_ids`；排除父级的排名排除全部父级。
Concepts 父级 containment 不足 1 只警告；Topics 按同一链产生集合，应严格满足
`f_joint = f_l1`（父级 pair），否则阻止发布。零频 L1 的 containment 为 NULL。

## 6. 计数与 NGD

```text
S_x = 归属节点 x 的不同 Work ID 集合
f_l0 = |S_l0|
f_l1 = |S_l1|
f_joint = |S_l0 ∩ S_l1|
ngd = [max(ln(f_l0), ln(f_l1)) - ln(f_joint)]
      / [ln(N) - min(ln(f_l0), ln(f_l1))]
```

计算每个 L1 与全部 L0 的笛卡尔积，不局限于父子。
NGD 对参数集合是对称的；文件以 L1 查询 L0 组织，并不宣称数学上有方向。
所有原始计数用非负 `int64`，分数用 `float64`，布尔保持 boolean。
采用自然对数；可用数学等价的稳定求值形式，但需记录实现与测试，不得改变公式。
禁止 epsilon、平滑、将零共现写为 1、或将分数截断到 [0,1]。

### 6.1 未定义与数值处理

保留全部节点与 pair，包括零频节点。增加 `ngd_status` 和 `quality_flags: list<string>`：

| 条件 | ngd | 主状态 |
| --- | --- | --- |
| 任一边际为 0 | NULL | zero_marginal |
| 边际均正但 joint=0 | NULL | zero_cooccurrence |
| 两边际均为 N，分母为 0 | NULL | zero_denominator |
| 有限正常结果 | 原 float64 值 | defined |
| 极小负值，[-1e-12,0) | 保留原值 | numerical_warning |

`zero_cooccurrence = (f_joint == 0)` 独立于主状态；零边际时仍为 true。
低于 -1e-12 或意外 NaN/Infinity 阻止发布，不静默变 NULL。容差进入计算配置。
公式未定义时不排名；NGD >1 是合法结果。

## 7. Schema 与派生指标

两套主矩阵使用同一 schema，主键 `(taxonomy, l1_id, l0_id)`：

```text
taxonomy, snapshot_version, run_identity
l0_id, l0_name, l1_id, l1_name
parent_l0_ids, parent_l0_names, parent_relationship_source
is_parent_pair
N, f_l0, f_l1, f_joint
ngd, ngd_status, zero_cooccurrence, quality_flags
joint_over_l1, joint_over_l0, jaccard
ngd_rank_for_l1, ngd_rank_excluding_parent
```

`joint_over_l1=f_joint/f_l1`，`joint_over_l0=f_joint/f_l0`，
`jaccard=f_joint/(f_l0+f_l1-f_joint)`；各自分母为 0 时 NULL。
NGD 未定义不意味着其他派生指标都未定义；例如正边际零交集的 Jaccard 为 0。

每个 L1 内对有限 NGD 升序 `dense_rank`，使用未舍入存储值；精确相等才并列。
第二个排名仅在非父级有限值子集计算，父级和未定义 pair 的该列为 NULL。
展示可四舍五入；ID 仅用于稳定输出顺序，不打破统计上的并列。
没有合格非父级时，“最近非父级”为空；并列最近时返回全部，不伪造唯一第一名。

## 8. Mathematics 切片

两套体系分别固定 Mathematics ID：Topics field 为 `https://openalex.org/fields/26`；
Concepts 从本次 L0 实体识别并核验后写入 metadata。不得跨体系替代或模糊匹配。
缺失/不唯一阻止对应切片正式发布。每个 L1 恰好一个 Mathematics pair，连零频和未定义也保留。

切片直接选择主矩阵，列重命名 `l0_*→math_l0_*`、`f_l0→f_math`、`ngd→ngd_to_math`；
保留 N、f_l1、f_joint、多父级列表、状态、flags、两个排名及 is_parent_pair。
数学本身是父级的 pair 不删除。切片中数值必须与原矩阵逐项一致，不能再算一遍公式。

## 9. 缓存与后续交叉分析

每个规范 Work 在 membership 缓存中一行，至少包含：

```text
work_id, work_id_numeric
publication_year, work_type, is_retracted, is_xpac
concept_l0_ids, concept_l1_ids, topic_field_ids, topic_subfield_ids
concept_source_list_state, topic_source_list_state, membership_quality_flags
```

ID 列表去重、稳定排序，采用 list 类型；缺失元数据保留 NULL。来源列表状态区分 null、empty、present。
异常证据另存压缩审计分片，通过 Work ID 和源分片定位；坏标签不被改写为正常空列表。
大规模 metadata 可使用已验证、同一快照的只读 Work 表关联，不复制全文或引用边。
Work ID 是后续撤稿/Disruption 联结键，关联前必须检查外部表的一对多关系。

保留每个已提交分片的 N、边际、joint 整数计数和完成标识，以便恢复和独立汇总校验。
仅当输入 Work 全局唯一且分片不重叠时可相加；不能跨分片重复计数。
全局四项计数支持在固定集合定义下重算 NGD、PMI、NPMI、Jaccard、条件概率等，
各指标的未定义情况另行处理。改变子总体须读取 membership 缓存重聚合；
改变 score 阈值、补祖先策略或 taxonomy 版本不能仅凭现有二值计数完成，需新版本重建。

## 10. 正式产物与压缩

```text
concepts_l0_l1_ngd.parquet
topics_l0_l1_ngd.parquet
concepts_l1_math_distance.parquet
topics_l1_math_distance.parquet
concepts_l1_l0_ranking.parquet
topics_l1_l0_ranking.parquet
taxonomy_nodes.parquet
taxonomy_parent_edges.parquet
membership/part-*.parquet
counts/part-*.parquet
audit/part-*.parquet                 # 有异常/审计记录时
ngd_metadata.json.gz
quality_report.json.gz
completion.json.gz
```

所有 Parquet 实际启用 ZSTD；计数/列表/布尔保持原生类型，不把数字或复杂列塞进 JSON string。
ranking 文件是矩阵的排序投影，保留全部 pair 与 NULL 排名，不另作统计。
taxonomy_nodes 保存节点层级、名称和边际计数，包含零频节点。
可选 CSV 仅限 `.csv.gz`；不默认输出未压缩 CSV/JSON。大型临时缓存和审计也必须压缩。
小型人工方法文档可用 Markdown/YAML；运行日志压缩归档。

## 11. Provenance 与发布

metadata 必须记录：快照 manifest 与验证证据哈希、源文件清单、N 定义与实测值、
覆盖率、两套 membership 规则、真实层级映射、节点清单、历史父级对象 URL/哈希/版本、
数学节点 ID、公式与求值实现、数值容差、异常策略、schema/calculation 版本、
代码 commit（若可用）和实际源码/config 哈希、dirty 状态、依赖版本、codec/级别、生成时间。
不能用 Git HEAD 代替未提交代码的真实身份。

输入、规则、schema、源码共同决定不可覆盖的 run_identity；仅并行数等资源参数可变，
每次调用另行记录。正式结果与未完成 staging 分离，压缩临时文件原子提交。
恢复必须核验 checkpoint 的来源、配置、输出哈希及覆盖，不因文件存在就跳过。
任何结构异常不得产生正式完成清单；可保留未完成数据供诊断。
验收通过后最后写 `completion.json.gz`：记录每个交付文件的 SHA256、行数、schema、
实际 codec、输入版本和质量报告哈希。正式已接受版本不可覆盖。

## 12. 性能与实施顺序

正式统计前必须比较 Go、Rust 与现有 PyArrow / DuckDB 列式方案，不能仅凭语言声誉
或以前的引用图基准选型。比较相同输入、相同精确统计和压缩交付的端到端性能，
另测统一解码输入上的计数内核，分辨解析、去重、聚合和 I/O 瓶颈。
实际不可用的工具链或库如实记录，不伪造横向测量；缺少候选实测须披露选型限制。
具体方案见 [BENCHMARK_PLAN.md](BENCHMARK_PLAN.md)。

本任务的计算对象是 Work—学科二值归属关系，不是 citation graph。不因“graph”名称
装载数十亿引用边；优先投影读取标签列，使用紧凑整数节点索引和去重集合表示。
可测试只读共享 membership、每 worker 私有计数矩阵、精确整数归并，避免全局锁竞争。
充分利用可用 CPU 和 RAM，但额外内存必须带来可测量收益，不以填满内存为目标。
无需新增网络数据库或网站依赖。

正式统计前实测含无标签、多标签和高标签数 Work 的分片，记录 wall time、CPU、
峰值/采样内存、读写量及压缩比，再确定并发、批次、缓存和实现；不能将小样本速度承诺为全库耗时。
初始资源上限 40 CPU、384 GiB RAM；所有数据/spill 位于 `/mnt/hg02`，新增产物最多 4 TB，
保留至少 1 TB 可用空间，监控其他作业负载，不停止或修改其他模块作业。

实施顺序：输入/关系冻结 → 小图 oracle 和数值测试 → 分片性能测试 → 全量 membership 与计数缓存
→ 矩阵/排名/切片 → 全量质量审计 → 完成清单。任何阶段不得用采样、近似或截断代替正式计数。
Go/Rust 并发模型本身不是性能证据，最终引擎必须有计数等价性与资源约束下实测报告支撑。
本文件是规范而非执行证据；实际阶段执行、失败恢复和验收结果见 `COMPLETION.md`。
