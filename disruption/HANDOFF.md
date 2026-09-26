# Disruption 交接（2026-09-27）

## 当前状态

全库引用图、年度稀疏统计、双口径窗口缓存已于 2026-09-25 完成。后续研究与 PPT
修订只读取冻结结果，没有因展示调整重新定义或重算引用网络。
本文件是交接摘要；正式完成证据见 [COMPLETION.md](COMPLETION.md)，统计契约见
[SPEC.md](SPEC.md)，全库运行方式见 [FULL_RUN.md](FULL_RUN.md)。
`OPERATIONS.md` 中“当前阶段”含早期开发日志，不应据此认为全库仍在等待运行。

## 冻结资产与入口

```text
/mnt/hg02/openalex-snapshot/analysis/disruption/full-runs/aa3884a2c445ca56fa6258f46e103e80dbbd382002f2eb3bd362d5066ea7777e/
```

- 输入快照：2026-06-26，全部 core + xpac，共 510,372,821 Works。
- 规范边 2,950,598,362 条；年度统计 1,724,927,348 行；窗口表 4,082,982,568 行。
- 每篇保留“不含发表年／含发表年”两套口径，各含 3y、5y、10y、lifetime。
- 查询先加载产物中的 `research/research_views.sql`、`research/custom_windows.sql`；
  用 `disruption_focal`、`disruption_research_ready`、`disruption_age_range()`，不要直接复制全库宽表。
- 原始大文件、压缩缓存、数据库、日志和产物不入 Git；仓库交付代码、文档和合成测试。

年度桶含年龄 0，支持约定范围内改变窗口而不重扫图。固定窗口的“不含发表年”取年龄
1…t，“含发表年”取 0…t−1。lifetime 仅累计至快照，不是最终一生；未成熟、未知或无定义
不得补成 0。没有有效参考记录不证明论文真实没有参考文献。

## 已有验证及边界

以下为完成记录中的历史验证，不是本次交接重新扫描全库：

- `completion.json`、`analytical/manifest.json`：全部 5,104 分片、完整覆盖和版本身份。
- `focal-window-integrity.json`：10,208 个 focal/windows 文件哈希及行数核验。
- `annual-quality/manifest.json`：全部年度文件与计数不变量核验。
- 独立小图 oracle、跨语言测试、32 个真实全图压力样本的新旧引擎逐字段对照；
  Python、Go、race、vet 的完成记录见 `COMPLETION.md`。

覆盖与完整性检查不是全图第二套算法复算。28,353,116 Works 的年度统计不可计算或
超出观察范围，仍保留记录；3,050,312 Works 的 OA 原始引用数与重建入度不同，只警告、
不改写。历史下载前 provenance 缺口仍保留，不能补造。
本次交接只确认了冻结完成文件存在并核对文档，不宣称重做上述昂贵验收。

## 下游研究与待办

下游为 [撤稿 × Disruption × NGD 研究](../research/disruption-ngd-2026-09/README.md)，
产物根目录是 `/mnt/hg02/openalex-snapshot/analysis/retraction-disruption-ngd/20260925/`。
其中研究主 CD 条件为成熟、不含发表年的 5 年窗口、有效参考数 ≥10、窗口被引数 ≥5；
这是下游筛选，不是本模块删除记录的规则。CDX 在本研究中指成熟窗口 CD，不是另一公式。

后续优先事项：

1. 修复下游 `disruption_analysis.py` 的缓存与代码身份绑定隐患，再用新目录重跑；
   这是研究层审计发现，不等于本模块全库缓存已被证明错误。
2. 扩展下游独立验收到最新版 PPT 和完整 provenance；不要用原始报告的验收覆盖新页。
3. 改图统计定义、参考集合或输入快照时创建新版本，禁止覆盖本冻结目录。
4. 确需全库重算时沿用已测资源约束：40 CPU、384 GiB RAM、无 swap，输出压缩；
   不因只改展示或研究阈值重复执行昂贵引用图计算。

提交与推送状态以 Git 历史为准；`COMPLETION.md` 末尾的“未提交”是交付当时的历史状态。
