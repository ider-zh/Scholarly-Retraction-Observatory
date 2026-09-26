# OpenAlex Disruption 数据计算与存储规格

规格版本：`disruption-spec-v1`。状态：设计约定；基础缓存与小图参照实现见 README，
**尚未完成全图网络统计**。
计划数据 schema：`disruption-v1`；实际 calculation version 与代码哈希在首次实现时登记。

## 1. 已确认的承诺边界

- 保存网络中间统计，研究纳入阈值与图构建分离；不预删低参考数、低被引数的论文。
- 同一快照、同一网络规则下支持任意整年边界窗口；不保证任意日期/周年窗口。
- 第一版派生指标为 CD 与 no-NR 两式；不声称三个计数足以重算任意 Disruption 变体。
- 可自由按 focal 的类型、年代、学科及阈值筛选。改变 reference/citing 层的类型、
  学科、作者自引或共同参考数规则，需要从持久边层重新计算，不保证只操作统计表。
- 同一快照内复用；跨快照增量维护另设任务。新版本不覆盖旧定义与结果。
- 两种窗口口径均保留，主分析默认不含发表年，包含发表年用于敏感性分析。
- 内部计数恒等式失败仅警告，不阻止发布结果；不能隐藏差异或伪造检查通过。

## 2. 节点与网络范围

节点、focal、reference 候选和 citing 候选均覆盖快照的 core + xpac Works、全部文献类型。
不得继承当前撤稿报告中的 article、角色或 core-only 筛选。保存 `is_xpac` 原值，
未知不当成 false；对 focal 筛选 core 不等于把引用网络改成 core-only。

一条规范引用边方向为 `citing_work_id -> referenced_work_id`。
节点逻辑主键为 `work_id`；跨快照物理数据集通过快照命名空间隔离。
使用原始 OpenAlex URL ID，并保存可无损转换的 `work_id_numeric`；转换失败保留异常，
不截断、不猜测 ID 或合并关系。所有大计数使用 64 位整数，不能使用浮点数存整数计数。

### 2.1 节点表 `works`

必须持久保存：

```text
work_id, work_id_numeric, doi
publication_year, publication_date, publication_date_precision
work_type, is_retracted, is_xpac
source_id, source_type, language
primary_topic_id, primary_topic_name, has_primary_topic
subfield_id, subfield_name, field_id, field_name, domain_id, domain_name
openalex_cited_by_count
has_valid_publication_year, date_quality_flags
```

可缺失属性保存 NULL，不删除节点。来源没有日期精度信息时登记 unknown，不能将填充的
完整日期当作已证实的日精度。学科采用该冻结快照的 primary-topic 层级；缺失不补推断值。
保留节点表是为了以后不再请求 OpenAlex API，并非宣布快照没有漏收或覆盖偏差。

### 2.2 原始边与规范边

- 原始层可使用每个 citing Work 的原始 reference 列表或等价边明细，保留原始值、
  重复项及其位置，使解析规则可复核。
- 规范边要求两端为可解析、存在于冻结节点集的 Work，移除 Work 指向自身的 self-loop，
  并按有向 ID 对去重。该处理不等于排除作者自引；第一版不实施作者自引过滤。
- 同年、逆序或年份未知的引用仍保留在规范边层，并打时间质量标记。
- 无法解析、端点缺失、自身引用等均进入审计信息。悬空 ID 不伪造完整 Work 节点。
- 必须支持按 citing 查询参考集合和按 referenced 查询 incoming 邻域；具体索引与
  分区实现由基准选择，不在规格中声称某种物理设计必然适合全量。

## 3. Reference set 与入度

对 focal `f`，第一版 `R(f)` 为规范边中满足 `year(reference) < year(f)` 的不同目标。
同年、未来年份或未知年份参考不进入该集合，但其边和异常计数保留。
缺少有效 focal 年份时，时间合格 reference set 无法判定，不把它标作空集合。

保存以下计数与字段，原始数组条目数与去重 Work 数不可混淆：

```text
reference_count_raw                 原始列表条目数；列表本身未知时为 NULL
reference_count_resolved_unique     规范边的不同 referenced Work 数，不加时间限制
reference_count_valid               严格更早年份的不同 reference 数；无法判定为 NULL
reference_count                     reference_count_valid 的兼容别名
has_references                      reference_count_valid > 0；未知则 NULL
reference_quality_counts            重复、无效、悬空、自身、同年、逆序、年份缺失等
graph_indegree_all                  所有规范 incoming 边的不同 citing Work 数，不限时间
incoming_same_year_count
incoming_earlier_year_count
incoming_unknown_year_count
openalex_graph_citation_count_delta graph_indegree_all - openalex_cited_by_count
```

质量类别可重叠，不默认可以相加。`reference_count_valid=0` 仅表示此快照与本规则下
没有合格 reference，不表示论文真实没有参考文献。源列表未知与已知空列表仍可通过原值区分。
无法判定时间归属的 incoming 分类计数允许 NULL；`graph_indegree_all` 仍可独立计算。

## 4. 年龄桶核心统计

逻辑粒度：`focal_work_id × age_year`，外加快照/计算版本命名空间。
`age_year = citing_publication_year - focal_publication_year`，存储所有可观测非负年龄桶，
不只计算到十年。无法定位年份的记录不被塞入 age=0，单列质量统计。

对每个桶，用不同 citing Work 计数，且 citing Work 不得等于 focal：

- `NF`：引用 f，但不引用 R(f) 中任何 Work。
- `NB`：引用 f，且引用 R(f) 中至少一个 Work。
- `NR`：不引用 f，但引用 R(f) 中至少一个 Work。

一个 citing Work 引用多个 R(f) 成员，仍只计一次 NB 或 NR。
不得把 reference 的入度相加来近似 NR，也不得按两跳路径数代替不同 Work 数。
age=0 表示同年网络关联，不证明 citing 真正发表于 focal 之后。

每桶保存：

```text
NF, NB, NR
citation_count                     同桶独立 incoming 计数路径计算
future_related_count               同桶局部邻域的独立去重数量
citation_count_consistent          citation_count == NF + NB
citation_partition_delta           citation_count - (NF + NB)
neighborhood_count_consistent      future_related_count == NF + NB + NR
neighborhood_partition_delta       future_related_count - (NF + NB + NR)
is_partial_calendar_year
```

这些等式是同规则下的数学恒等式；按项目决策，失败后输出 warning、差值与受影响范围，
继续保留结果。不改写独立计数来强行对齐。源 `cited_by_count` 的差异属于另一类检查。

## 5. 双窗口契约

| `window_policy` | k 年的年龄桶 | 2020 年论文的 5y |
| --- | --- | --- |
| `exclude_publication_year` | 1 到 k，含端点 | 2021-01-01 至 2025-12-31 |
| `include_publication_year` | 0 到 k−1，含端点 | 2020-01-01 至 2024-12-31 |

包含发表年的起点是统计自然年起点，不宣称论文在 1 月 1 日已经发表。
两套标准窗口至少提供 3y、5y、10y、lifetime，并支持由年度桶组合其他整年范围。
比较 2021—2025 与 2020—2024 同时改变起止边界；若只研究加入 age=0 的影响，
另算 2020—2025 并明确它是扩展窗口，不将其也命名为标准 5y。

`lifetime`：exclude 从 age=1，include 从 age=0，均截至该快照；它不是最终一生。
保留 `future_citation_count_lifetime_exclude_publication_year` 与
`future_citation_count_lifetime_include_publication_year`，不要用含糊的
`citation_count_lifetime` 同时表示时间窗口计数与全图入度。

### 5.1 观察完整度

每个窗口保存 `planned_start_date`、`planned_end_date`、`observed_end_date`、
`observed_age_start`、`observed_age_end`、`is_mature`、`computation_status`。
有限窗口只有在计划结束日不晚于快照截止日时才成熟；当前快照年份的桶标为部分年度。
日期/年份不合法时成熟度为 NULL，不猜测。快照截止并不保证数据库没有收录延迟。

未成熟窗口的计数明确命名为 observed counts，是计划范围与快照范围交集的结果；
保留 `raw_score_observed`，完整窗口解释性 score 为 NULL。尚未进入观察范围的窗口
不可填零。lifetime 没有有限的计划结束日，`is_mature=NULL`、`snapshot_limited=true`，
不能因为该 NULL 把所有 lifetime 分数排除。

保存 `paper_age_at_snapshot = snapshot_year - publication_year` 作为描述量，
不拿它直接判断成熟。`max_observable_years` 不作为含糊通用字段；用上述边界、
`observed_age_end` 与两种 policy 各自的完整年度数替代。

## 6. 派生分数、状态与阈值

```text
CD    = (NF - NB) / (NF + NB + NR)
no-NR = (NF - NB) / (NF + NB)
```

公式严格使用 NF/NB/NR；即使独立 citation count 检查发出警告，也不换分母或修改公式。
两式分别检查分母。`NF=NB=0, NR>0` 时 CD 为 0、no-NR 为 NULL。
没有有效参考时 raw 公式可能等于 1，但解释性 score 为 NULL，保留 `no_references`。
缺年份、缺统计或分母为零均不得伪造有效分数。

分别保存公式定义状态、观察状态、数据质量状态和 policy eligibility。
标记包括但不限于 `no_references`、`no_future_citations`、`empty_denominator_cd`、
`empty_denominator_no_nr`、`insufficient_observation_window`、`incomplete_record`、
`snapshot_limited`、`citation_partition_warning`。多个标记可同时成立；
若提供单个展示主状态，必须登记优先级，不能取代完整标记。

`has_valid_publication_year`、`has_valid_reference_graph`、`has_valid_citation_graph`
必须有可执行检查定义；未知为 NULL，不能仅因任务退出成功就全部置 true。
后两项仅表示本次快照构图与质量规则的检查结果，不代表真实世界引用图完整。

reference/citation 阈值及组合 eligibility 从数值和 policy 派生，不作为保留条件。
`has_ref_1/5/10/20`、citation 阈值、`eligible_r10_c10_5y` 等可以是视图字段；
含糊窗口别名仅可在明确绑定一个 `window_policy` 的视图中使用。
未成熟/未计算/未知输入的 eligibility 不自动记 false。公式有效不等于研究上可靠。

## 7. 物理层与稀疏语义

使用四层逻辑数据资产：节点、原始/规范边、年度长表、窗口结果。
持久分析结果优先采用分区 Parquet，SQL/dataframe 可读；是否增加数据库或索引由基准决定。
窗口长表主键含 `(work_id, window_policy, window)`；宽表作为交付视图或物化表，
每个 Work 一行，包含 policy 后缀，或为每种 policy 各交付一张有明确版本的宽表。

节点表保留所有 Work。年度表可稀疏存储，但配套覆盖范围及完成清单，必须能够区分：

1. 已完成且桶在可观察范围内：缺行可以展开为真实零。
2. 未完成、缺合法 focal 年份或不在观察范围：不可展开为零。
3. 完整计算但存在一致性 warning：保留计数与 warning，不与未完成混淆。

完成清单记录输入/配置哈希、覆盖的 focal 分区、分区内排除或不可计算记录、输出校验值、
统计量和完成状态；只有输出原子落盘并验证后才更新清单。单个文件存在不等于已完成。
未知或损坏分区不可对外宣称完整。warning-only 约定不授权把损坏数据读成成功结果。

## 8. Provenance 与研究关联

每批结果至少绑定：快照日期与 manifest SHA-256、来源 prefix、输入分片及校验信息、
节点/边范围、去重/时间/reference/window policy、schema version、calculation version、
代码/配置哈希、生成时间、执行参数、质量统计与警告清单。
批次元数据可集中存放；所有输出通过 batch ID 可追溯，宽表交付视图展开关键版本字段。
修复公式、改变规则或更新快照必须产生新版本，不静默覆盖。

保留既有 `retrospective-v1` 接受政策及下载前 manifest/传输日志缺口，不声称新建模块
补齐了历史证据。未提供的删除映射不可自行推断。

后续撤稿分析仅通过明确匹配的 Work ID 关联。RW 未匹配项标记未关联，不能赋零。
撤稿与非撤稿论文的比较必须绑定同一快照、图规则、窗口 policy 与 eligibility。
field/year percentile 或 z-score 属于第二阶段，其比较总体、缺失学科、零方差、
并列排名与小样本处理另设版本；不得默认只在撤稿子集中标准化。

## 9. 执行与验收

先实现 [ACCEPTANCE.md](ACCEPTANCE.md) 的手工图测试，再执行分层基准；本规格落地不授权
立即启动全图扫描。资源上限：40 逻辑 CPU、384 GiB 总 RAM，新增磁盘最多 4 TB，
同时保留至少 1 TB 可用空间；总结果、索引、临时空间都计入预算，以较严格约束为准。
大文件与 spill 写 `/mnt/hg02` 外部目录，不写仓库、根盘 `/tmp` 或 `public/`。

遇超预算风险先暂停并提供估算与替代执行方案；不静默近似、截断高入度节点或缩减总体。
目录布局、分区数量和进程分配由实测决定，不把资源上限当作性能保证。
首次全量验收须记录准确性、覆盖率、未计算项、警告、磁盘/内存峰值、运行时间和恢复验证。

## 10. 定义参考

- [Funk 与 Owen-Smith 原始网络指标论文](https://public.websites.umich.edu/~jdos/papers/A_Dynamic_Network_Measure_of_Technological_Change.pdf)。
- [作者 cdindex 实现文档](https://cdindex.readthedocs.io/en/latest/_modules/cdindex/cdindex.html)。

这些资料不自动决定本项目的自然年窗口。本文的双窗口和异常处理是显式研究约定；
未经独立核对，不宣称结果与采用日期周年窗口的其他实现逐值一致。
