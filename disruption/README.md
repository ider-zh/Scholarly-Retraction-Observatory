# OpenAlex Disruption 离线计算

状态：**全库年度统计、双口径窗口缓存和独立质量审计已完成**。
覆盖 510,372,821 Works；未满足定义或观察条件的结果保留 NULL，不强制生成分数。
实际验收证据、数据位置与查询方法见 [COMPLETION.md](COMPLETION.md)。

目标是保存可复用的引用网络统计，再由研究层选择有效性阈值、比较总体及归一化方法。
后续撤稿研究通过 OpenAlex Work ID 关联这些结果，而不是只在撤稿论文子图上计算。

## 目录

| 路径 | 用途 |
| --- | --- |
| [SPEC.md](SPEC.md) | 已确认的数据范围、双窗口、统计定义、存储及版本契约 |
| [ACCEPTANCE.md](ACCEPTANCE.md) | 待实现的手工图、质量检查与验收标准，不是已通过的测试报告 |
| [src/README.md](src/README.md) | 可运行的压缩节点与原始引用缓存 |
| [tests/README.md](tests/README.md) | 缓存、恢复与输入校验测试 |
| [reference/README.md](reference/README.md) | 小图精确参照算法与双窗口测试 |
| [engine/README.md](engine/README.md) | Go 双向 CSR、精确年度计数与真实压力样本 |
| [benchmarks/RESULTS.md](benchmarks/RESULTS.md) | 实测压缩、Go/Rust 性能与选型边界 |
| [OPERATIONS.md](OPERATIONS.md) | 作业运行、查询进度及恢复方式 |
| [FULL_RUN.md](FULL_RUN.md) | 全库自动接续、压缩结果与严格完成条件 |

依赖方向：外部冻结快照 → 节点/边层 → 年龄桶统计 → 窗口结果 → 撤稿关联及分析。
不修改 `pipeline/` 的既有研究总体，不改变现有 `public/data/`，不加入网站构建或定时刷新。

## 数据位置

代码、小型合成测试图和设计文档可以提交 Git。完整节点、边、统计结果、数据库、
运行日志及 spill 必须写入外部目录。当前基础缓存使用：

```text
/mnt/hg02/openalex-snapshot/analysis/disruption/foundation/
  <snapshot_manifest_sha256>/
    <calculation_config_sha256>/
      run.json
      input_inventory.json
      shards/<source_key_sha256_prefix>/
        nodes.parquet
        raw_references.parquet
        complete.json
```

基础缓存已完成 2,446 个分片、510,372,821 Works，压缩输出约 35.95 GB（十进制）。
原始引用条目 3,086,374,182，不等于去重后的规范边数。
图与统计作业位于同级 `bridge/`、`jobs/<job_config_sha256>/`；状态见 `python disruption/status.py`。
根盘 `/tmp` 只用于小型检查，不承担生产数据存储。目录内 `.gitignore` 提供额外防误提交保护。

## 已完成的计算链

1. 已实现小图参考算法、Go 引擎与 Parquet 导出的跨语言一致性测试。
2. 全部节点及原始引用压缩缓存已完成，保留来源与校验信息。
3. 完整双向索引、32 个真实压力样本及新旧引擎逐字段对照完成。
4. 全部年度统计和双窗口 Parquet 缓存完成，无采样、近似或高连接截断。
5. 研究视图、自定义年度窗口查询、去重撤稿关联示例已生成；未修改公开报告。

现有引用缓存只覆盖特定撤稿目标，不能作为全量图或完整 NR 邻域。
现有快照的回溯验证接受政策与历史传输证据缺口必须继承记录，不能因新模块而抹去。
