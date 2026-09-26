# 精确引用图与年度统计引擎

Go 标准库实现，使用共享只读双向 CSR，不按 core/xpac、类型、学科或撤稿状态裁剪引用网络。
节点 ID 索引顺序沿用桥接输入，不保证 Work ID 数值排序；统计分片用 `graph_node_index` 排序。

## 实现范围

- `graph.go`：全节点索引；两遍分片引用扫描；规范边去重、端点解析、自环排除及审计；
  同年、逆序、未知年边保留在规范图。ID 映射与逆向 CSR 填充目前为串行，引用扫描及数组压缩并行。
- `count.go`：严格更早年份的 reference set；所有已观察年龄桶的精确 NF/NB/NR，
  citing Work 去重；直接引用数独立累计，缺年份与未观察范围不填零。
- `main.go`：构图、明确选择 focal、真实高连接压力样本。全量统计必须显式传 `--all`。

```bash
cd disruption/engine
go test -race ./...
go vet ./...
go build -trimpath -o /mnt/hg02/openalex-snapshot/analysis/disruption/bin/engine .
```

上面的通用构建路径用于手工操作；已启动服务使用带二进制 SHA-256 的不可变文件名。
不要覆盖运行中作业使用的二进制。

```bash
engine build --input BRIDGE/manifest.json --output GRAPH
engine count --graph GRAPH --output ANNUAL --benchmark-size 8 --workers 4
engine count --graph GRAPH --output ANNUAL_SUBSET --focal-ids work-ids.txt --workers 40
```

生产命令应放在 `OPERATIONS.md` 所述 cgroup 下。`GOMEMLIMIT` 只是软限制，
不能替代 384 GiB 硬上限。计数线程各自保留候选集合，不复制整图；极端节点仍可能
需要很大的候选集合，因此初次尾部基准用 4 个 worker，而非盲目开启 40 份大 scratch。

## 持久契约

桥接输入采用 gzip little-endian 二进制，原始 Parquet 仍永久作为审计来源：

- 节点每行 32 字节：uint64 Work 数字 ID、int32 年份（0 未知）、uint32 保留位 0、
  int64 来源被引数（-1 未知）、int64 原始引用条目数（-1 未知）。
- 引用每行：uint64 citing ID、int64 列表长度（-1 未知）、随后该数量的 uint64 reference ID。
  非法、空值或超出 uint64 的引用编码为 0，原始文本保留在 foundation；重复条目不在桥接时删除。
- 每个输入与数组缓存都有完整 SHA-256；图 manifest 必须 complete，不能用 partial 桥接构图。
- 图数组使用 gzip BestSpeed 分别压缩；输出 manifest 保存来源、快照、schema/计算版本、
  构建引擎 SHA-256 和生成时间。目录原子发布，不覆盖已有版本。
- 年度输出是压缩 JSONL 分片与完成 manifest；经 `window_results.py` 流式生成
  ZSTD Parquet 的 focal、annual、windows 三表。完成且可观察范围内的稀疏缺行才可补零。

计数一致性失败只记 warning，不改写观测值。结构损坏、版本不符或输入不完整仍拒绝执行。
构图阶段暂不提供扫描中途恢复；若构图失败，从完整桥接重建。年度计数按已提交分片恢复。

## 压力样本不是全库统计

`--benchmark-size 8` 分别选高入度、高 reference 数、高有效 reference incoming 暴露量、
等间隔图节点，合并去重后至多 32 个 focal；每个 focal 使用完整引用邻域，绝不截断。
暴露量只用于选择昂贵查询，不能代替 NR。样本不代表总体分布，不能直接估算全库平均耗时。
每个 focal 保存耗时、访问边数与不同候选 Work 数；是否扩展全量需据实测再决定。

测试包含固定手工图、随机图、异常引用、压缩索引 roundtrip、SHA 损坏、恢复与竞态检测。
Python 跨语言集成测试覆盖 foundation 格式 → 桥接 → Go 图/年度 → 双窗口 Parquet，
并逐 Work、逐年龄桶及窗口与独立 Python oracle 对照。
