# NGD 离线运行

本模块只读冻结快照，不调用 OpenAlex 在线 API，不修改 Disruption、网站数据或其他作业。
正式结果位于 `/mnt/hg02/openalex-snapshot/analysis/taxonomy-ngd/<run_identity>/final/`。
没有 `final/completion.json.gz` 的目录不是正式结果。

## 运行顺序

```bash
python -m unittest taxonomy_ngd.test_ngd -v
python -m unittest discover -s taxonomy_ngd/tests -p 'test_*.py' -v
python -m taxonomy_ngd.run prepare
python -m taxonomy_ngd.run benchmark --run <上一步输出目录>
python -m taxonomy_ngd.run run --run <上一步输出目录>
```

生产命令应置于 CPUQuota=4000%、MemoryMax=384G、MemorySwapMax=0 的作业单元。
Go/Rust 编译器须在该单元的 PATH 中；Python 使用本机含 DuckDB、PyArrow 的环境。
同时限制 OMP/BLAS 隐式线程。正式阶段默认使用实测最快的引擎和 worker 配置，
可用 `--workers` 在 1…40 范围调整资源，不改变版本身份或统计定义。

`definition.json.gz` 固定输入文件清单、Parquet footer/stat 身份、分类实体完整 SHA256、
历史父级对象校验、验证报告和计算源码身份。原始大文件的身份检查不是完整内容 SHA256，
不应把 footer 校验宣传为全部源文件字节重哈希。
membership、counts、audit 的每个结果文件都有完整 SHA256。

## 压缩缓存与恢复

- `staging/part-*/` 保存分片 membership、counts、audit，均为 ZSTD Parquet。
- `complete.json.gz` 在三个输出写完、同步、校验后提交；没有它的分片会重算。
- 恢复先验证配置、源身份、产物 SHA256、schema、行数和 codec；损坏分片不会被静默跳过。
- 中断留下的 `.tmp` 仅在本作业锁内重建，不将其当作完成结果。
- `scan_quality.json.gz` 汇总来源异常。结构异常允许完成扫描/缓存，但阻止正式发布。
- `progress.json.gz` 是进度信息，不替代进程存活检查或最终完成清单。

全量验收另查所有 Work 的跨分片唯一性，并从完整 membership 重新执行独立 SQL 聚合，
对照各分片计数之和。正式矩阵不由基准样本外推。

## 撤稿关联示例

```sql
WITH selected AS (
  SELECT DISTINCT work_id FROM matched_retraction_works
  WHERE work_id IS NOT NULL
)
SELECT membership.*
FROM read_parquet('<final>/membership/part-*.parquet') membership
JOIN selected USING (work_id);
```

若用筛选后的 membership 重算距离，必须重新计算该子总体 N，并保存新分析版本。
不能沿用全库 N、不能把多条撤稿来源记录重复算作多篇 Work。

## 边界

当前 NGD 是学科标签集合的共现距离，不是论文文本语义距离、引用网络距离或因果效应。
Topics 使用全部已附带 topic；Concepts 不按 score 筛选、不补祖先。
层级包含关系、标签覆盖和全集规模都会影响距离，NULL 不能填为 0 或 1。
