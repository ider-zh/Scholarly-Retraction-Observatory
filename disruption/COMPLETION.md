# Disruption 全库交付与验收

验收日期：2026-09-25（Asia/Shanghai）。快照日期：2026-06-26。
本交付是冻结快照的离线辅助数据，不代表 OpenAlex 在线最新状态，也不修改网站聚合。

## 数据与位置

```bash
RUN=/mnt/hg02/openalex-snapshot/analysis/disruption/full-runs/aa3884a2c445ca56fa6258f46e103e80dbbd382002f2eb3bd362d5066ea7777e
```

| 资产 | 实际完成规模 | 压缩大小（十进制） |
| --- | ---: | ---: |
| 全库 Work | 510,372,821 | focal Parquet 24.93 GB |
| 规范引用边 | 2,950,598,362 | 双向图分数组 gzip 缓存 |
| 年度稀疏统计 | 1,724,927,348 行 | annual Parquet 10.73 GB |
| 双口径窗口统计 | 4,082,982,568 行 | windows Parquet 32.99 GB |
| 年度计算原始缓存 | 5,104 分片、全部 Work | JSONL gzip 52.61 GB |

全部 core + xpac Works 保留，不按类型、引用数、学科或撤稿状态删除。
每个 Work 有两套口径各 3y、5y、10y、lifetime，共八行窗口结果。
年度桶包含年龄 0 及全部已观察年龄；两套口径只改变观察年龄范围，不改变有效参考集合。
规范边去重、去除 Work 自身环；原始 3,086,374,182 条引用列表条目另行保存并带审计。

## 实际验收证据

- `completion.json`：全量覆盖、版本及来源哈希；生产服务正常退出，`ExecMainStatus=0`。
- `analytical/manifest.json`：5,104 分片、连续全图索引、每个窗口组唯一 Work 覆盖、所有源分片哈希及结构校验。
- `focal-window-integrity.json`：独立重查全部 10,208 个 focal/windows 文件的 SHA256 和 Parquet 行数，全部通过。
- `annual-quality/manifest.json`、`quality.json`：独立重查全部年度文件哈希、schema、行数；1,724,927,348 行中负数、内部 citation/neighborhood 不一致及错误 flags/deltas 均为 0。
- `analytical/quality.json`：逐窗口状态、成熟度、退化条件和来源差异；原始计数保持独立，不为消除警告而改写。
- 完整图上 32 个压力样本，新稠密引擎与旧稀疏引擎逐字段一致；Python 测试、Go 测试、race 检查和 vet 通过。
- 实际生产 SQL 视图绑定成功；真实 Work `W2396084620` 的四组自定义年龄范围与对应缓存窗口计数一致。

不将小图或单篇验证冒称全图独立算法复算。全量证据涵盖覆盖、文件完整性和计数不变量；算法等价性由独立小图 oracle、随机图测试和真实压力样本对照支持。

## 查询入口

DuckDB 依次执行 `$RUN/research/research_views.sql` 和 `$RUN/research/custom_windows.sql` 的文件内容。

- `disruption_focal`：一篇一行，含原始/有效参考计数、全图入度和审计信息。
- `disruption_annual`：年度稀疏统计，不能不检查观察范围就补零。
- `disruption_research_ready`：Work × 口径 × 窗口，关联完整元数据、成熟度、阈值和质量标记。
- `disruption_work_wide`：一篇一行，两套口径写在列名后缀中；这是惰性查询视图，不额外复制数十亿行。
- `disruption_age_range(2, 5)`：从年度缓存重算年龄 2…5；4y、7y 示例在 `custom_window_examples.sql`。
- `matched_retractions.sql`：用户提供规范 Work ID 匹配表后，先 DISTINCT 再关联；未匹配结果保持 NULL。

查询总体很大，交互探索应先明确 focal 条件；全库宽表查询仍需要足够资源。
`research_ready` 的无后缀 `computation_status`/观察范围属于窗口，自动后缀 `_1` 对应 focal 字段。
图质量标记为版本化的有限检查，不能证明真实参考文献或索引收录完整性；详见 `research/POLICY.md`。

## 解释与限制

- 28,353,116 Works 的年度时间统计不可计算或超出观察范围，记录仍保留，不填零。
- 3,050,312 Works 的 OA 原始引用数与重建全图入度不同，已保留来源值和警告；不能把八窗口重复标记相加当作独立论文数。
- 没有有效参考文献不等于真实没有参考文献；未成熟窗口保留已观察计数/raw 分数，标准分数为 NULL。
- lifetime 是截至快照的累计观察，成熟度为 NULL，不承诺完整一生。
- 接受回溯验证的历史下载 provenance 缺口继续保留，未补造下载前证据。
- field/year normalization、其他边权/多重共同引用等新变体不是本次第一阶段数据构建交付；已有年度统计支持约定范围内重筛选和重算。

## 运行资源

生产上限 40 CPU、384 GiB RAM，禁止 swap；完整计数使用共享只读 Go 图和每 worker 去重缓存。
因微批次等待调度瓶颈，批次从 1,000 调至 10,000，使用同一二进制和统计配置恢复；旧调用参数保留。
实测高计算量阶段约使用 39.3 核；观测内存约 203.3 GB，不能将观测值冒称精确历史峰值。
全部年度分片于 09-25 05:58 完成，32 进程窗口转换于 07:44 完成。
验收时整个 disruption 产物目录约 217.69 GB（含旧版本/中间缓存），远低于 4 TB 上限；磁盘剩余约 5.3 TiB。

代码和文档仅在本地工作树；未提交、推送或部署。
