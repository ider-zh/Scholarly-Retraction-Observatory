# 计算代码与缓存

`cache_foundation.py` 提供全类型、core + xpac 节点投影及原始 reference 列表缓存。
它只负责基础缓存，不产生规范边、NF/NB/NR 或分数。后续层已新增：

- `graph_bridge.py`：核验 foundation 后转为 Go 可读取的 gzip 数值流；partial 输入仅可缓存，禁止构成生产图。
- `../engine/`：完整规范引用图与精确年度统计。
- `window_results.py`：完整年度分片转换为 focal、annual、双口径 windows 三张 ZSTD Parquet 表。
- `../advance.py`：受资源保护的分阶段运行器，只自动推进至真实压力样本，不自动启动全库计数。

依赖复用 `pipeline/snapshot_requirements.txt` 中的 DuckDB 与 PyArrow。
SQL 在 DuckDB 原生引擎执行，Python 负责分片调度，非逐行 Python 图计算。

```bash
python disruption/src/cache_foundation.py --workers 16 --max-files 2
python disruption/src/cache_foundation.py --workers 16
```

首条命令选择最大的两个输入文件进行 pilot；第二条在相同配置版本中续算全量。
默认输出 `/mnt/hg02/openalex-snapshot/analysis/disruption/foundation/`，按 manifest、
配置和实现代码 SHA-256 分版本；不写入仓库。更改 worker 数不会改变数据定义版本。

每进程使用一个 DuckDB / Arrow CPU 线程；默认 65,536 行批次，ZSTD level 1 Parquet。
`--workers` 上限 40，`--memory-gib` 上限 384。调度器监控聚合进程 RSS，并逐批检查
至少 1 TB 剩余磁盘和至多 4 TB 新增占用。磁盘预算为十进制 TB，内存为 GiB。
生产启动仍应使用 systemd/cgroup 硬内存及 CPU 上限，避免轮询保护前的瞬间超限。
其他进程消耗磁盘也会触发保守暂停，不能把它当成只针对缓存的精确用量计费。

完成文件经完整 SHA-256 校验后原子提交 shard checkpoint；续算校验输出哈希。
输入与已接受 `retrospective-v1` 验证清单的路径、大小、mtime、行数绑定，并保存
所有分片的不可变 footer 指纹。输入校验是 stat + Parquet footer，**不是输入全文哈希**，
不能检测同时保留大小、mtime 和 footer 的刻意正文改写。下载前 provenance 缺口继续保留。
仅有文件、没有 checkpoint 的产物不算完成；`pilot_complete` 不表示快照全量覆盖。

`--allow-small-test-disk` 仅用于合成测试，使测试可以在临时目录运行；不得在生产使用。

建议后续职责：快照/节点读取、边解析与索引、时间及 reference policy、精确年度计数、
窗口派生、质量审计、断点恢复、撤稿关联。模块之间通过 SPEC 定义的字段与版本连接。

可以复用经过核查的 I/O 和 manifest 校验工具；不得隐式导入撤稿报告的 article/core-only
纳入规则，也不得用现有 RW 目标引用缓存代替全图。新依赖在实现时独立声明，
不为尚未实现的代码预先安装工具或注册 CLI。
