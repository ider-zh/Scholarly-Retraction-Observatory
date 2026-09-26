# 撤稿 × Disruption × NGD 交接

更新：2026-09-27，Asia/Shanghai。

## 已完成与不可混用的口径

- OA发表队列2000–2025：220,305,891篇，撤稿标记77,414篇；RW–OA匹配撤稿样本58,345个不同Work，按最早可解析撤稿事件年2000–2025选取。两个样本不能相加，RW构成比例不能替代OA学科内分母。
- Concepts按原附带L0/L1多标签归属；Topics撤稿归属按primary_topic。NGD为全部core+xpac标签共现属性，Topics距离使用全部topics，不能称为文本语义或数学方法使用量。
- 主CD：发表次年起5个完整自然年、已成熟、有效参考≥10、窗口被引≥5。保留11种预设口径。含发表年为年龄0–4，不含发表年为1–5；lifetime仅截至快照，不是统一时长。
- 同学科年×类型分层对照：共同层内标记组减未标记组均值，按标记组有效论文数加权，不是一对一匹配或因果估计。
- RW“先结束组”：CD观察期完整结束时间严格早于撤稿日期，不是从撤稿日倒推或截短观察窗。

## 已核实的主要发现

| 分类层级 | 主CD与OA标记占比ρ | 学科数 |
| --- | ---: | ---: |
| Concepts主学科 | −0.444 | 19 |
| Concepts子学科 | +0.048 | 284 |
| Topics主学科 | −0.049 | 26 |
| Topics子学科 | −0.211 | 248 |

- Concepts主学科11口径均负，范围−0.739至−0.328；不能外推为单篇论文保护效应。Concepts子学科8正3负；Topics子学科11口径均负，范围−0.457至−0.088。
- 分层散点两轴比较同一个CD组间差值的前后版本：Concepts217点、Topics128点；214/217、124/128方向保留，204/217、118/128分层后下移。成斜带不是新的独立强相关。
- 数学NGD与子学科标记占比ρ：Concepts −0.061、Topics +0.104；年份标准化后−0.080、+0.112。均较弱，不支持跨体系普遍的“近数学、低占比”。
- 高比例父级内NGD相关图的“C:数学”是16个数学子学科的距离—占比ρ=−0.159，不是CD或数学与自己的距离。
- 近/中/远在每个父级内部按全部有定义NGD的插值三分位划分，分别≤下分位点、两点之间、>上分位点；并列不拆、NULL不分组。然后取N≥1,000子学科比例的组内中位数，不合并重叠标签的分子分母。

## 当前PPT与历史版本

- **当前交付**：https://www.kdocs.cn/l/cl717MhQQ4UJ
- 云文件ID：`83xyWT2ZB1MWpK7owVqF1xmE6RRDjsQDg`；本次交付记录为version2、58页，操作前重新查版本/哈希。
- 第42页新增分组解释，第43页近远组图；第51–56页附表明确ρ＝学科平均CD/no-NR与同学科OA标记占比的Spearman相关，不是NGD相关。原图表数值未改。
- 已补充CD/NGD/ρ概念、窗口、敏感性参数AND组合、章节过渡、分层图解释、颠覆度结论和图旁ρ值。
- 早期概念版 https://www.kdocs.cn/l/cfuQq1ulunhV 出现云端新版本。下载403，局部文字写入返回成功但回读未生效；没有整文件覆盖。当前交付是此前本地版本派生副本，不声称已合并该旧链接上的外部修改。
- 最初37页：https://www.kdocs.cn/l/cmAukYuG1npB ，保留不动。
- WPS可能替换中文字体；本地和实际云端PDF均已检查，不声称像素完全相同。

## 文件与复现

结果根目录：
`/mnt/hg02/openalex-snapshot/analysis/retraction-disruption-ngd/20260925/`

- 根目录`presentation.json`为冻结37页原始报告，不是最新PPT。
- 最新目录`reader-groups-rho-revision/`含58页payload、PPTX、本地render、实际云端PDF、回读文本、revision/interpretation审计、delivery_manifest和kdocs_delivery。
- `reader-revision/`、`reader-window-revision/`、`reader-sensitivity-revision/`、`reader-conclusion-revision/`、`reader-ngd-correlation-revision/`保留各阶段版本。
- `aggregates/`、`report-statistics.json`、`ngd-ranked/`、`ngd-controls-final/`、`global_main_metrics.json`是解释和图表的冻结证据。

```bash
PY=/home/ider/miniconda3/bin/python
PPTPY=/tmp/retraction-kdocs-20260916/venv/bin/python
CODE=research/disruption-ngd-2026-09
ROOT=/mnt/hg02/openalex-snapshot/analysis/retraction-disruption-ngd/20260925
OUT=$ROOT/reader-groups-rho-revision
$PY "$CODE/revise_report.py" "$ROOT"
$PPTPY "$CODE/build_deck.py" "$OUT/presentation.json" "$OUT/研究报告_概念导读修订版.pptx"
$PPTPY "$CODE/render_deck.py" "$OUT/研究报告_概念导读修订版.pptx" "$OUT/render"
$PY -m unittest discover -s "$CODE" -p 'test_*.py' -q
$PPTPY -m unittest discover -s "$CODE" -p 'test_builder.py' -q
```

当前28项研究测试执行成功，含1项因分析环境无python-pptx跳过的模块；独立PPT环境4项排版测试通过。58页本地/云端页数核对，文字越界检查为零，修改页截图抽查通过。这些不等于全库算法复算。

## 最近只读统计审计

- 独立平均秩实现/SQL复算44组CD相关、545组分层差异，与现有结果一致。
- 独立复算276组非退化NGD相关、581组间接标准化结果，一致。
- 核对11,948个NGD pair的集合约束；11,929个定义值符合公式、19个正确未定义。
- 未重新扫描5.10亿Work或重算完整引用网络；没有发现会推翻当前主要数值的算术错误。

## 已确认但尚未修复的问题

1. `disruption_analysis.validate_cache/initialize_run/aggregate`仅检查缓存可读，配置未绑定计算代码；改逻辑后可能复用旧结果，却给manifest写入新代码哈希。小样本已复现；当前冻结结果未发现受影响。应绑定不可变代码版本和输入摘要，拒绝过期缓存，不重新归属旧结果。
2. `verify_results.py`只自动核验根目录旧PPT，图点验证主要覆盖NGD，不完整覆盖最新58页、CD相关与分层图。`scientific_review`输出另一个JSON，但不与报告逐项断言。应支持指定最新payload并使用独立算法核对。
3. 验收器忽略Disruption manifest的`provenance`字典。当前手动哈希相符，但自动验收必须补齐。
4. 图中分层样本筛选与文字的“未标记合格数≥100”未完全共享同一代码谓词；当前所有217/128点均满足，暂无数值影响。未来应统一选择函数。

优先修复以上研究层可复现性/验收问题并添加回归测试；不要借修复改变研究分母、门槛或覆盖既有结果。新研究口径须新版本。仓库只提交代码与说明，不提交外部数据、云凭据、PPT/PDF/截图。
