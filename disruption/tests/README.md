# 合成数据测试

按 [验收标准](../ACCEPTANCE.md) 将手工小图转成独立自动化测试；测试数据须为小型合成图。
`test_cache_foundation.py` 已实现缓存层测试，不访问或扫描生产全图：

```bash
python -m unittest discover -s disruption/tests -p 'test_cache_foundation.py' -v
```

覆盖原始列表重复/空/未知值保留、全部类型与 xpac 保留、ID 解析、日期质量标记、
ZSTD、空分片、输入变化、输出损坏、未提交产物恢复、磁盘保护、manifest 行数检查，
以及真实子进程 CLI 的 pilot→全量续算。小图计数与双窗口测试见 `../reference/`；缓存测试通过
不等于 Disruption 算法或全图结果已经验收。

优先覆盖 reference 去重、citing Work 去重、双窗口、成熟度、缺失/零、警告策略、
年度长表与窗口视图的一致性、输入/结果哈希和断点恢复。测试不得访问或扫描生产全图。
优化算法必须与小图参考实现逐 focal、逐桶精确对照。
