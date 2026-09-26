# 基础缓存运行说明

## 当前阶段

2026-09-23 完成 Go/Rust 合成基准、真实列压缩基准、全量 footer 清点。
首批最大的 8 个分片试跑成功：3,200,000 Works、73,069,044 原始引用条目，
输出合计 550,581,912 bytes，采样汇总进程 RSS 峰值约 5.11 GB。
这些数字不是规范边数量或 Disruption 统计结果；单分片 worker 耗时约 8.8–13.8 秒，
不将其作为包括启动、源清单核验的整个试跑耗时。

随后启动用户级服务 `disruption-foundation-20260923.service`，40 个分片 worker，
每个 worker 的 Arrow/DuckDB 线程数均为 1。压缩为 ZSTD level 1，batch 65,536 行。
服务资源限制 40 CPU、384 GiB RAM、350 GiB MemoryHigh、禁止该作业使用 swap。
挂载盘报告为旋转磁盘；40 worker 是并发上限而非 40 核利用率保证，缓存阶段可能受
磁盘寻道与带宽限制。图计算的共享内存并行结果不能套用为分片 I/O 的加速比。
低 RAM 占用不表示没有利用资源：列投影是流式任务，不为占满 RAM 而复制数据；
共享图索引与 scratch 的大内存预算在后续网络统计阶段使用。

## 查询、停止与恢复

```bash
python disruption/status.py
systemctl --user status disruption-foundation-20260923.service
journalctl --user -u disruption-foundation-20260923.service -n 30 --no-pager
systemctl --user stop disruption-foundation-20260923.service
```

停止命令仅供需要暂停时使用，当前不会自动执行。硬中断后 `run.json` 可能仍显示 running，
因此同时检查 service；只有 `complete.json` 的分片可复用，残留 partial 文件不表示成功。
`status.py` 只汇总 checkpoint，不重新校验大文件 checksum，也不证明进程存活。

首次启动或清理已结束的同名服务后，在仓库根目录执行：

```bash
systemd-run --user --unit=disruption-foundation-20260923 \
  --property=WorkingDirectory="$PWD" \
  --property=MemoryMax=384G --property=MemoryHigh=350G \
  --property=MemorySwapMax=0 --property=CPUQuota=4000% \
  --property=RemainAfterExit=yes \
  --setenv=OMP_NUM_THREADS=1 --setenv=OPENBLAS_NUM_THREADS=1 \
  --setenv=MKL_NUM_THREADS=1 --setenv=NUMEXPR_NUM_THREADS=1 \
  /home/ider/miniconda3/bin/python -u disruption/src/cache_foundation.py \
  --workers 40 --memory-gib 384
```

不要并发启动相同版本目录；锁会拒绝重复作业。用户服务用于会话外运行，
不承诺服务器重启后自动恢复。恢复时重新运行同一版本命令，完整校验已经提交的输出，
坏 checksum 直接报错，不静默覆盖。源文件变化直接拒绝；代码/配置变化生成新命名空间。

## 数据契约与完成标准

默认输出：`/mnt/hg02/openalex-snapshot/analysis/disruption/foundation/`。
运行路径由 snapshot manifest SHA-256 与代码/配置 SHA-256 决定，见 `status.py` 输出。
生产输入必须匹配已有 `validated-source.json` 和其 `files.json`；
继承 retrospective-v1 与传输证据缺口，不伪造下载前记录。

分片成功要求行数核对、输出原子替换、完整 SHA-256 与 checkpoint 原子提交。
全量 `run.json` 为 complete 且全部 2,446 分片完成才算基础缓存完成。
`--allow-small-test-disk` 只用于合成输入，生产禁用该绕过参数。
当前依赖沿用已安装 DuckDB 1.4.4、PyArrow 23.0.1；不增加网站构建依赖。

限制：程序的 4 TB 新增磁盘保护按文件系统空闲空间净变化估计，不是目录配额。
其他作业删除数据可能掩盖新增量，其他作业写入则可能提前触发保护；不要把此检查
宣称为严格的输出目录硬配额。当前缓存远低于预算，大规模索引阶段须增加目录用量保护。
RSS 是采样值，生产硬上限由服务 cgroup 保证；达到硬上限可能终止作业，已提交分片可恢复。

本轮实际检查：14 项小图参照测试、7 项缓存测试通过；另外核对 3 个真实分片的输出
SHA-256、行数、ZSTD codec，并逐值比较首批 65,536 行原始 references；全部通过。
合成内核 18 次运行匹配独立 Python 校验和。不等于已完成全图计数验收。

## 图与统计开发进度

基础缓存现已 complete：2,446 分片，510,372,821 Works，3,086,374,182 原始引用条目，
35,953,512,251 bytes 压缩输出。引擎与导出实现见 `engine/README.md`。
真实桥接试跑 8 分片、2,731,734 Works、17,579,981 原始引用条目，gzip 输出
110,674,097 bytes；该试跑 manifest 为 partial，不能拿它计算生产网络统计。

当前服务 `disruption-advance-20260924.service`：等待完整 foundation → 全量压缩桥接 →
完整 Go 规范图 → 至多 32 个真实压力 focal 的全邻域精确年度计数 → 双窗口 Parquet。
桥接 16 worker，图阶段最多 40 线程；初次高连接计数 4 worker，以限制候选集合峰值。
服务总限额 40 CPU、384 GiB RAM、禁用 swap，Go 软限制 300 GiB。
每 10 秒检查整个 disruption 输出根目录实际文件字节数及剩余空间；达到 4 TB / 1 TB
保护阈值会终止当前子任务并保留已提交产物。检查有轮询间隔，并非文件系统硬配额。

```bash
python disruption/status.py
systemctl --user status disruption-advance-20260924.service
journalctl --user -u disruption-advance-20260924.service -n 30 --no-pager
```

`jobs/<配置哈希>/state.json` 记录阶段、命令、状态和错误，`graph/manifest.json` 是完整
索引的发布标记，`benchmark-annual/manifest.json` 记录样本年度分片，`analytical/` 保存三表。
需要暂停时停止该服务；再次使用相同 `advance.py --foundation ... --engine ...` 命令
与相同资源约束可恢复桥接/统计分片。构图中途尚无恢复点，会从完整桥接重新构建。

年度压力样本通过不代表全库统计完成；程序明确停在 benchmark_complete，不自动执行
`count --all`。未完成任务、未知年、未成熟窗口仍不填零。尚需实测真实压力样本的耗时、
访问量及内存，再决定全库年度作业调度与资源分配；未修改既有网站或公开聚合。

2026-09-24 完整性复核后，加固了基础分片所属配置、输入清单指纹和图缓存来源匹配检查，
以及年度完成 manifest 的 fsync。旧 `disruption-advance-20260923` 在桥接阶段主动停止，
其 job 明确记录 interrupted；新作业独立版本化，旧基础缓存不受影响。
当前验证：25 项 Python 缓存/桥接/窗口/跨语言测试、14 项 Python oracle 测试、
12 项 Go 测试均通过；Go race detector 与 vet 通过。真实全图结果仍以作业 manifest 为准。

已知扩展限制：当前 `count --all` 默认每 1,000 focal 一分片，并逐分片重写清单及检查目录，
在 5.10 亿 focal 规模会有过多小文件与二次增长的元数据工作。全量生产前需要优化
分区粒度和分层完成清单；本轮自动作业只做有完整邻域的有限压力样本，不触发该路径。

后续全库授权与实现已接续：见 [FULL_RUN.md](FULL_RUN.md)。生产现在使用新 `full` 命令，
不是上述旧 `count --all` 路径；稠密线程缓存、长期 worker 池、流式大分片和独立完成
checkpoint 已解决上述扩展问题。`disruption-full-20260924.service` 自动等待当前图/基准
作业完成后执行全部年度统计与压缩分析表导出，不能将等待或启动状态误报成完成。
