# OpenAlex 学科标签共现 NGD

状态：**全量计算、压缩缓存和独立验收已完成（2026-09-25）**。
覆盖 510,372,821 Works；Concepts 5,396 个 pair，Topics 6,552 个 pair。
数据位置、实际检验及限制见 [COMPLETION.md](COMPLETION.md)。

本模块独立构建可复用的学科集合共现距离层，后续可通过规范 OpenAlex Work ID
与撤稿、Disruption 等数据关联。不依赖撤稿子集，不接入网站构建，不修改既有统计。

- [SPEC.md](SPEC.md)：总体、membership、分类关系、矩阵、缓存与版本契约。
- [ACCEPTANCE.md](ACCEPTANCE.md)：实现前冻结的测试用例和全量交付验收要求。
- [BENCHMARK_PLAN.md](BENCHMARK_PLAN.md)：Go、Rust 与列式工具的实测选型及 CPU/RAM 并行利用门槛。
- [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md)：实际候选比较与并发扩展结果。
- [OPERATIONS.md](OPERATIONS.md)：运行、恢复、压缩缓存与撤稿关联示例。

两套结果独立保存：Concepts 原生 level 1 × level 0；Topics subfield × field。
当前快照实体清单对应 5,396 和 6,552 个 pair；这些是本次输入的预期，不是算法常量。
本模块测量的是**基于快照学科标签共现的 NGD**，不是单篇语义距离或因果效应。

代码、测试与文档放在本目录；正式数据、中间缓存、日志和 spill 放在外部目录：

```text
/mnt/hg02/openalex-snapshot/analysis/taxonomy-ngd/<run_identity>/
```

正式产物已写入外部目录，未写入 Git 或网站聚合。未提交、推送或部署。
