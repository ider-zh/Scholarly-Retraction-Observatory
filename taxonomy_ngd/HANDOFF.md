# 学科 NGD 交接（2026-09-27）

## 当前状态与资产

全库标签共现 NGD、membership 压缩缓存及独立验收已于 2026-09-25 完成。
本文件是近期下游研究的交接摘要，不替代 [SPEC.md](SPEC.md)、
[COMPLETION.md](COMPLETION.md) 和 [OPERATIONS.md](OPERATIONS.md)。

```text
RUN=/mnt/hg02/openalex-snapshot/analysis/taxonomy-ngd/46194db71c3b1c538ce87257994318307a066c9708ca9038d8a0d48233ba9319
FINAL=$RUN/final
```

- 冻结快照：2026-06-26。共同全集 N=510,372,821，保留全部 core + xpac。
- Concepts 原生 L1 × L0：284 × 19，共 5,396 pair。
- Topics subfield × field：252 × 26，共 6,552 pair。
- 数学切片分别 284／252 行；逐 Work membership 共 2,446 个分片。
- 正式文件约 8.69 GB，数据为 ZSTD Parquet，元数据为 gzip；不纳入 Git。
- 正式发布以 `final/completion.json.gz` 为准，不把 staging 或 progress 当交付。

Concepts 使用全部附带标签，不设 score 门槛、不补祖先；Topics 使用完整 topics 列表，
不是 primary_topic。数学锚点为 `https://openalex.org/C33923547` 和
`https://openalex.org/fields/26`。NGD 是学科标签集合的共现距离，不是单篇文本距离、
数学方法使用量或颠覆度 CD；全集大小、标签覆盖和层级包含关系会影响其值。

## 已有验收与限制

历史验收记录见 `final/quality_report.json.gz`、`independent_acceptance.json.gz`、
`source_oracle.json.gz`、`resources.json.gz`、`reuse_provenance.json.gz`：

- 10 项测试；全库身份唯一性、全部 membership 的 SQL 边际／joint 精确重算。
- 7,348 个交付文件的哈希、大小、行数、schema、codec 检查；全部矩阵公式与排名复核。
- 10,240 篇真实论文的原始标签独立集合 oracle；不冒称全库原始标签的第二次解析。
- Concepts 全部有定义；Topics 有 19 个正边际零共现 pair，保持 NGD=NULL。
- Concepts 历史父子 361 个 pair 中 359 个包含率不足 1，保留警告而不补标签。

本次交接确认正式完成文件存在、核对已有文档，没有重新执行上述全库检查。
源大文件 footer/stat 身份不是完整字节 SHA256；历史下载前证据缺口仍保留。
正式扫描使用实测 Go 混合方案，40 workers；验收曾因全局 SQL 内存限额失败，改为
32 worker 分片 SQL 精确重算后完成，失败尝试没有从记录删除。详见
[BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md)。

## 近期撤稿研究如何使用

下游 [研究目录](../research/disruption-ngd-2026-09/README.md) 复用上述全库 NGD，
作为外部学科属性；没有把研究样本重新冒称全库距离。
研究产物在 `/mnt/hg02/openalex-snapshot/analysis/retraction-disruption-ngd/20260925/`。

需要特别向读者区分：

- 下游 Topics 撤稿占比按 primary_topic 分类，但这里的 NGD 来源仍是全 Topics 多标签。
- NGD 章节的 ρ 比较“子学科与数学的 NGD”和“同子学科 OA 撤稿标记占比”；
  CD 附录的 ρ 则比较“学科平均 CD/no-NR”和“同学科 OA 撤稿标记占比”。
- 全子学科原始关联为 Concepts ρ=−0.061、Topics ρ=+0.104，均较弱；
  不从符号差异推断强关系或因果，不将其读成数学自身的 CD。
- “近数学／远数学”在各主学科内按有效 NGD 的第 33.3%／66.7% 分位点划组。
  近组 ≤ 第一分位点，远组 > 第二分位点，同值不拆分；之后保留发文 N≥1,000 的
  子学科比较各自撤稿比例的中位数，不把组内分子分母直接合并。
- 分界点按主学科独立确定，不是跨领域通用距离阈值；不能将零共现 NULL 当作 0。

最新解释性 PPT 的本地产物在 `reader-groups-rho-revision/`，共 58 页；
当前补充副本为 https://www.kdocs.cn/l/cl717MhQQ4UJ 。该副本不声称合并原云文档
未同步的编辑；完整修订历史、证据与后续云端操作以研究目录交接为准。

## 下一步与恢复原则

1. 优先复用冻结 NGD；只有研究总体或标签规则改变时，从 membership 重新计算
   N、两边际和 joint，使用新版本目录，不能只替换分母或沿用旧排名。
2. 关联撤稿时先按规范 Work ID 去重，未匹配记录保持 NULL。
3. 推进研究层缓存身份绑定和最新版报告独立验收，不因解释文本调整覆盖全库结果。
4. 重跑前阅读 `OPERATIONS.md`：40 CPU、384 GiB RAM、无 swap，压缩输出；
   不并发写同一版本，不自动重启已经完成的生产作业。

提交与推送状态以 Git 历史为准；旧文档中的“未提交”描述当时的交付状态。
