# 学科 NGD 全库交付

完成日期：2026-09-25。输入是冻结的 **2026-06-26 OpenAlex Parquet 快照**，不是在线实时数据。

## 正式产物

```bash
RUN=/mnt/hg02/openalex-snapshot/analysis/taxonomy-ngd/46194db71c3b1c538ce87257994318307a066c9708ca9038d8a0d48233ba9319
FINAL=$RUN/final
```

两个体系共用全部 core + xpac 的 **N=510,372,821**，没有因为缺标签、类型或撤稿状态删论文。

| 结果 | 规模 |
| --- | ---: |
| Concepts 原生 L1 × L0 | 284 × 19 = 5,396 pair |
| Topics subfield × field | 252 × 26 = 6,552 pair |
| Concepts → Mathematics 切片 | 284 行 |
| Topics → Mathematics 切片 | 252 行 |
| 逐 Work membership | 510,372,821 行，2,446 分片 |

每套矩阵另有完整排名文件，包含全部 pair、NULL 排名和多父级信息。
Mathematics ID 分别为 `https://openalex.org/C33923547` 和 `https://openalex.org/fields/26`。
全部交付文件合计 **8,693,773,475 bytes（约 8.69 GB，十进制）**，其中 membership 约 8.63 GB。
Parquet 实际使用 ZSTD，元数据/质量/完成清单为 gzip；未生成大规模未压缩 CSV。

## 覆盖与质量

| 覆盖项 | Works |
| --- | ---: |
| Concepts 有任意附带标签 | 471,242,621 |
| Concepts 有 L0 | 464,337,686 |
| Concepts 有 L1 | 375,050,467 |
| Concepts 同时有两层 | 374,958,996 |
| Topics 有 field/subfield | 395,089,475 |

这些覆盖数不替换公式中的全库 N。Concepts 使用全部附带 ID，包括零分/低分；不补祖先。
Topics 使用完整 topics 列表，映射并去重 field/subfield，计算跨标签的全部 pair，不用 primary_topic 回填。

- 非法/悬空标签、内嵌链冲突、Work 身份冲突等结构异常：**0**。
- Concepts 5,396 个 NGD 均有定义。
- Topics 6,533 个有定义，**19 个正边际零共现 pair 保持 NGD=NULL**，不平滑或填 0/1。
- Topics 父级包含关系全部满足精确计数要求。
- Concepts 历史父级的 361 个 pair 中，359 个包含率不足 1，已保留警告；未因此补标签、删论文或更改距离。

这测量的是标签集合共现距离，不是单篇文本语义距离或因果效应。标签覆盖、集合大小、
层级包含关系和共同 N 都会影响结果；不能脱离这些限定比较数值。

## 实际验收

1. 10 项测试通过：独立八 Work 集合、未定义与大于 1 的 NGD、并列排名、多标签跨父级、
   零分标签、缺失列表、异常阻断、损坏/中断恢复、Go/Rust 等价、全局重复 ID 和不可覆盖发布。
2. 全库 Work 唯一性、规范列表去重/排序、来源身份复核通过。
3. 从**全部 membership 文件**另用 SQL 精确重算边际与 joint，逐分片汇总与生产原生计数完全一致。
4. 独立验收器读取全部 **7,348 个交付文件**，复核 SHA256、大小、行数、schema 和实际压缩 codec。
5. 全部矩阵 pair 的原始计数、对数差形式 NGD、派生比例、dense rank、排名投影和数学切片逐项通过。
6. 原始 taxonomy 全表与缓存 lookup 完全一致；五个分片共 **10,240 篇真实论文**用独立 Python 集合
   从原始标签重建 membership、核对元数据/列表状态，并重算该子总体，与缓存一致。

证据：`final/completion.json.gz`、`final/quality_report.json.gz`、`independent_acceptance.json.gz`、
`source_oracle.json.gz`、`resources.json.gz`、`reuse_provenance.json.gz`。
小样本 oracle 不冒称全库独立原始标签重解析；全库验收覆盖所有缓存文件、身份与精确计数。

## 性能与失败恢复

选型见 `BENCHMARK_RESULTS.md`：三种方案的输出语义一致；Go 混合方案端到端实测最快，
使用 40 workers 完成原始扫描与缓存。Go/Rust 负责精确整数计数，DuckDB/PyArrow 负责列式读取、
标签解析、压缩写入与验证，并非宣称整个流水线由单一语言完成。

首轮全局 SQL 关联验收触及 256 GiB 查询内存限额，未发布正式结果。
后将**验收阶段**改为 32 worker 的分片 SQL 精确重算和整数归并，不改变 membership、计数或公式。
旧缓存全部重新校验后以硬链接复用，旧目录保留；新 run_identity 记录发布实现变化。
基准复用只因投影、计数及基准源码未变，来源路径/哈希和理由已记录，不假称重新测量。

恢复验收作业 cgroup 记录峰值约 **38.28 GiB**，正常退出 `ExecMainStatus=0`；
原始失败尝试的资源日志也保留，不把失败尝试从性能记录中删除。
所有作业限制为 40 CPU、384 GiB RAM、无 swap；磁盘余量保持在 1 TB 以上。
来源历史回溯验证与缺少下载前证据的限制继续保留。

## 使用

```sql
SELECT l1_name, l0_name, ngd, f_joint, N, ngd_rank_excluding_parent
FROM read_parquet('<FINAL>/concepts_l0_l1_ngd.parquet')
WHERE ngd_rank_excluding_parent = 1
ORDER BY l1_name, l0_id;
```

上式保留所有并列最近非父级，不伪造唯一最佳项。其他派生指标可使用 N、两边际和 joint 重算。
更换研究子总体须从 membership 重新聚合 N/边际/joint；不能只改分母或复用全库排名。
撤稿关联去重示例见 `OPERATIONS.md`。未更改网站、Disruption 或公开聚合；未提交、推送、部署。
