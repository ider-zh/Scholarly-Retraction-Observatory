# 全库统计执行与验收

当前状态：2026-09-25 全量年度统计、窗口转换及独立审计已完成。
下文保留执行过程和恢复方法；最终数字与交付入口以 `COMPLETION.md` 为准。

2026-09-24 用户授权继续完成全部统计、数据处理与缓存。本任务的完成目标不是压力样本：
必须覆盖完整快照的 510,372,821 Works，保留所有可观察年度统计，并交付两套口径的
3y、5y、10y、lifetime，共 4,082,982,568 行窗口结果。未知/未成熟仍按 SPEC 保留 NULL。

## 正在执行的依赖链

2026-09-24 00:58（Asia/Shanghai）实测进度：全图压缩缓存已经完成，
包含 510,372,821 节点、2,950,598,362 条规范边；32 个压力样本及其窗口转换完成。
全量计数服务已进入分片提交，日志确认至少 75 个分片、7,500,000 focal 已落盘。
这不是全库完成声明，后续进度以服务日志和已提交 checkpoint 为准。

1. `disruption-advance-20260924.service`：完整桥接、全图索引、真实压力样本。
2. `disruption-full-batch10k-20260924.service`：从原 `disruption-full-20260924.service` 的检查点恢复，加载同一全图；
   使用稠密线程缓存重新计算压力样本，逐字段对比旧稀疏实现，再计算全部 focal。
3. 全部年度分片提交后，并行转换 focal / annual / windows 三表到 ZSTD Parquet。
4. 全量检查窗口组身份覆盖、索引连续性、行数、质量状态、文件哈希，才发布 completion。
5. 完成后另行生成研究查询侧表，不修改已固定哈希的统计产物；再进行最终人工验收。

两项服务存在先后依赖，完整计数不会与构图并发争抢资源。
工作流允许使用 40 CPU、384 GiB RAM，使用 cgroup 硬限额、禁止 swap。
每 20 秒检查共享产物根目录 4 TB 和剩余 1 TB 约束；轮询不是文件系统硬配额。

## 生产实现

- `engine/full.go` 使用 100,000 focal 分片、10,000 focal 微批次；约 5,104 分片，
  不再使用旧计数命令的约 51 万小分片方案。
- 长期存活的 worker 复用去重代际标记，每个节点 4 字节；40 worker 的稠密标记约
  81.66 GB，按需分配，不复制共享图，也不保存巨大的 touched-node 列表。
- 没有有效参考文献的 focal 精确走直接引用路径，不分配不必要的去重标记。
  该优化没有删除零参考或低被引记录。
- 分片流式 gzip 写入；文件、checkpoint 和目录同步后才提交；最后一次性写完整清单。
  断点恢复先验证既有分片，再继续；可调整 worker/微批资源参数，不更改数据定义。
- `src/bulk_results.py` 使用 32 进程转换并验证结果，每分片保留独立完成清单。
  生成质量汇总和关联 foundation 元数据的 DuckDB `views.sql`，供后续阈值、学科、年代筛选。

合成基准中稠密缓存约为旧稀疏实现的 3.1 倍速度；10,000 focal 的八窗口转换约
4.71 秒。它们不是全库耗时保证；真实高连接邻域与共享磁盘负载必须以实际作业记录为准。

## 查看与恢复

```bash
python disruption/status.py
systemctl --user status disruption-full-batch10k-20260924.service
journalctl --user -u disruption-full-batch10k-20260924.service -n 30 --no-pager
```

产物位于 `/mnt/hg02/openalex-snapshot/analysis/disruption/full-runs/<配置哈希>/`：

```text
state.json
annual/job.json
annual/invocation.json
annual/progress.json
annual/checkpoints/*.json
annual/annual-*.jsonl.gz
annual/manifest.json
analytical/partitions/part-*/{focal,annual,windows}.parquet
analytical/progress.json
analytical/quality.json
analytical/views.sql
analytical/manifest.json
completion.json
```

`active_partition_rows_processed` 只是内存/临时文件进度，尚非已提交结果。
缺少完成清单、作业退出异常或覆盖率不足时，不能宣布完成或把缺失当作零。
完整结束必须同时核对 `completion.json`、全部源/结果清单、质量检查与服务退出状态。
运行中的源代码和二进制已固定哈希；若代码变化，应启动新版本，不能混用旧定义。

## 完成后的研究查询层

### 运行资源调整记录

2026-09-24 02:01（Asia/Shanghai）将微批次从 1,000 调整到 10,000，保留 40 workers、
原引擎二进制、图版本、100,000 行分片和统计配置哈希。旧服务停止后启动新服务恢复，
已提交分片重新校验，未提交分片重算；原调用参数保存在 `annual/invocation-batch1000.json`。
调整依据是真实分片中每篇耗时差异很大，批次屏障造成空闲：两片的调度模拟表明计数部分
可能由约 10.6/11.9 秒降到 6.4/7.3 秒。该估算不是实际加速结论，须查看恢复后的吞吐。

### 查询层生成

```bash
python -m disruption.src.research_views \
  <full-run>/analytical/manifest.json <foundation>/run.json \
  <prerequisite>/graph/manifest.json <full-run>/research
```

该步骤只接受已完成、来源链一致的全库产物，输出独立的 `research_views.sql`、
`POLICY.md`、`matched_retractions.sql` 与来源清单。它不更改计数、分数或现有 SQL 文件，
也不会删除不满足阈值的论文。查询视图提供参考文献阈值、窗口引用阈值、年龄和窄定义的
图质量标记；有限窗口未成熟时引用阈值返回 NULL，lifetime 不因此被屏蔽。
质量标记的具体定义见产物 `POLICY.md`，不能将其解释为真实文献记录完整性的保证。
撤稿接入示例先对 Work ID 去重，避免一篇论文多条撤稿记录导致重复计数。
来源链验证不等于重新校验所有大文件；最终验收仍须检查全量统计的覆盖和质量证据。

查询层同时输出一篇一行的 `disruption_work_wide` 视图、两种口径的完整自然年数、
`custom_windows.sql` 与 4y / 7y / 年龄 2…5 查询示例。自定义窗口只读取年度缓存，
仅对完成且可观察的稀疏桶补零；未知、未计算和完全未来的范围保持 NULL。

### 独立年度质量汇总

```bash
python -m disruption.src.annual_quality \
  <full-run>/analytical/manifest.json <full-run>/annual-quality --workers 32
```

该审计重查全部年度 Parquet 的文件哈希、结构、行数和每行计数关系，防止年度正负差值
在累计窗口中相互抵消而漏报。计数不一致、错误的 consistency flags/deltas 仅产生警告，
不覆盖来源值；负数、必要字段缺失、文件损坏或覆盖不全才作为结构性失败。
输出独立且不可覆盖的 `quality.json` 和来源清单，不修改固定版本的统计数据。

主流水线及独立年度审计均已完成；未改动公开报告聚合，未提交、推送或部署。
