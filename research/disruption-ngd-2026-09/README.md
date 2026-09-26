# 撤稿学科 × 颠覆度 × NGD 探索研究

## NGD相关系数补充版

当前同一补充版链接已扩展至58页（50页正文、8页附录）：第42页增加主学科内NGD三分位划组说明，第43页保留原近远组图；第51–56页明确ρ为学科平均CD/no-NR与同学科OA撤稿标记占比的Spearman相关，不是NGD相关。图表数值和口径不变。最新产物在`reader-groups-rho-revision/`，之前57页保留在`reader-ngd-correlation-revision/`。当前`revise_report.py`输出至最新目录；下方较早版本构建示例的目录须相应替换。

独立副本：https://www.kdocs.cn/l/cl717MhQQ4UJ 。第37页直接显示两套分类的数学距离—撤稿占比ρ，第38页明确年份标准化对照。基于上一轮本地57页版本生成，不改变统计数值。原云文档版本已变化；为避免覆盖未同步的云端修改，未整文件替换原链接。原文件下载返回403，直接局部文字接口返回成功但回读未生效；副本不声称包含新增的云端编辑。原链接仍保留。

## 概念导读修订版

新版金山演示文稿：https://www.kdocs.cn/l/cfuQq1ulunhV 。本次在同一链接补充分层散点解释和颠覆度章节结论；51页、52页、55页版本分别保留在本地 `reader-revision/`、`reader-window-revision/`、`reader-sensitivity-revision/`，最初37页云文档和原始统计文件不变。

针对从上一版撤稿统计进入的新读者，增加术语铺垫、可编辑引用示意图、计算算例和四张章节分隔页。新版共57页：49页正文（含4页章节过渡）、8页附录。全部11张实证图的数值与原报告逐项一致，原有统计表数值全部保留；更新相关组名、列标题和敏感性图类别文字。仅从已有散点派生描述性计数和中位数，不重算网络统计、不改动原分析。

- 第4页：OA撤稿标记、n/N与RW样本构成的区别。
- 第7–12页：CD含义、NF/NB/NR图解、公式算例、双窗口与敏感性分析。
- 第13–14页：Spearman ρ的方向、强弱、并列名次与0.8算例。
- 第21–22页：观察期须在撤稿前完整结束的定义、2015年发表的时间例子，以及“先结束组”的原有对照结果。
- 第23–26页：完整口径参数表、观察年限示例、敏感性图与实际结论。Topics子学科11种口径均为负，Concepts子学科8正3负；不能表述为“Topics普遍不相关”。
- 第27–28页：相同CD均值差在发表年/文献类型分层前后的比较，解释散点成斜带、下移和方向保留，区别于CD与撤稿占比相关。
- 第30页：颠覆度章节结论，区分Concepts/Topics主学科和子学科，以及学科间与学科内比较。
- 第32–34页：NGD的共现直觉、频次数值例子及公式。
- 第2、6、31、46页：四章过渡；原始发现概览移动至附录，不在解释概念前先抛系数。

第37页已直接标出数学NGD与撤稿标记占比的Spearman ρ：Concepts −0.061（284个子学科），Topics +0.104（252个子学科）；系数合并同体系的事件数量颜色组计算。第38页明确为同一关系的年份标准化对照（−0.080、+0.112）。`ngd_reader.py`从原图独立计算平均秩相关，与冻结相关表匹配后才生成注释，不改图中数值。

新版文件均放在外部产物目录的 `reader-ngd-correlation-revision/`；上版保留在 `reader-conclusion-revision/`。文件包括`研究报告_概念导读修订版.pptx`、`render/`、`revision-audit.json`、`interpretation-audit.json` 和 `kdocs_delivery.json`。

```bash
PY=/home/ider/miniconda3/bin/python
PPTPY=/tmp/retraction-kdocs-20260916/venv/bin/python
CODE=research/disruption-ngd-2026-09
OUT=/mnt/hg02/openalex-snapshot/analysis/retraction-disruption-ngd/20260925
$PY "$CODE/revise_report.py" "$OUT"
$PPTPY "$CODE/build_deck.py" "$OUT/reader-ngd-correlation-revision/presentation.json" "$OUT/reader-ngd-correlation-revision/研究报告_概念导读修订版.pptx"
$PPTPY "$CODE/render_deck.py" "$OUT/reader-ngd-correlation-revision/研究报告_概念导读修订版.pptx" "$OUT/reader-ngd-correlation-revision/render"
```

`test_revise_report.py`验证证据不变与教学算例；`test_builder.py`在PPT环境验证章节页和引用图。无python-pptx的分析环境会明确跳过排版测试，而不是假称执行成功。

`sensitivity_reader.py`将22个敏感性图数值逐一与冻结统计表核对，再生成结论和轴标签；`test_sensitivity_reader.py`验证数值不可被“改标签”掩盖、正负方向声明与参数表。条件在同一行内以AND组合，各行独立作为替代方案；不是全因素组合实验。改变观察窗后，被引门槛在新窗口上应用。

`disruption_reader.py`逐项核对345个分层散点，派生方向保留、下移计数和中位调整量；从四个分类层级的既有11种口径生成章节结论。`test_disruption_reader.py`验证原图不变、证据不一致时报错及结论方向检查。Concepts主学科11种口径均为负不能外推成单篇论文保护效应；Topics按primary_topic归类，不沿用Concepts多标签重叠解释。

## 已确认设计

本研究沿用 https://www.kdocs.cn/l/cgrIJBxx1mWs 的既定样本，不修改既有网站数据。

- RW–OA 主样本：58,345 个不同 Work，最早可解析 RW 撤稿事件年 2000–2025；不要求 OA 撤稿标记为真。
- OA 比例总体：发表年 2000–2025、220,305,891 篇合格文献，其中 77,414 篇带撤稿标记。
- 保留 core、全类型、有效日期及原论文识别规则；RW 构成比例不能解释成学科内撤稿率。
- Concepts 使用全部附带 L0/L1 多标签，子节点不默认交集父标签；保留多父级。Topics 使用 primary_topic 的 Field/Subfield。
- NGD 优先复用已完成的全 core+xpac、全 Topics 多标签共现距离，作为外部学科属性；数学为主，计算机和物理为补充。NULL 不填零。
- 主 CD：不含发表年、完整成熟 5 年、有效参考数 ≥10、窗口被引数 ≥5。
- 敏感性包括无额外数量门槛（仍要求定义成立）、参考数 5/20、被引数 0/10、3y/10y/lifetime、含发表年及 no-NR。用户的 CDX 指成熟窗口 CD，不是另一公式。
- 学科 CD 按合格论文等权平均，补充中位数、四分位数、正值比例和覆盖率；不以个别显著性结果定结论。
- 发文 N≥1,000 的一级学科按 OA 标记比例选最高四分之一；全部学科仍保留。事件 n<20 标低事件数但不删除，合格 CD N<100 不进入主要相关分析。
- 数学 NGD 连续分析为主，同父级子学科近/中/远分组为辅；不得依据撤稿结果选择距离分组。
- 另行控制发表年份/文献类型，并核查 RW 撤稿前已结束的观察窗口；只能解释关联，不声称预测或因果。
- 保留零、未知、观察不足和小样本的区别；调整方法须记录版本及原结果。

## 执行与交付

外部产物目录：`/mnt/hg02/openalex-snapshot/analysis/retraction-disruption-ngd/20260925/`。
仓库只存源码、测试与研究说明；大缓存使用压缩 Parquet/JSON，不放入 Git。
复用已冻结 Disruption 与 NGD 清单，单独校验本研究总体、关联覆盖和产物哈希。
使用现有 `/tmp/retraction-kdocs-20260916/venv/bin/python` 制图与制作可编辑 PPTX。
云端交付为新建金山演示文稿，不覆盖既有报告。主文 24–30 页、深色背景浅色内容，附方法与敏感性分析。

初版交付：统计完成，已生成 30 页正文＋7 页附录的深色研究报告，包含 11 张原生可编辑图表。

金山在线演示文稿：https://www.kdocs.cn/l/cmAukYuG1npB 。新建文件，未覆盖原报告；已回读验证完整 37 页。

结果摘要见 [RESULTS.md](RESULTS.md)。外部产物目录包含：

- `研究报告.pptx`：可编辑本地备份。
- `render/研究报告.pdf`、`render/slide-01.png` 至 `slide-37.png`：本地渲染 PDF 和逐页截图。
- `金山云端导出.pdf`：实际云端导出的 PDF，不是本地渲染的替代声称。
- `研究数据表.xlsx`：11 张工作表，保留完整预设口径、分子分母、质量标记和敏感性结果。
- `disruption_manifest.json`：44 个 CD 汇总、4 个基线和4 个分层表的来源及哈希。
- `independent_crossstudy_verification.json`：全部 581 个学科基线、30,446 行 CD 汇总、1,839 个 NGD pair、1,083 个父子交集、536 个图中散点及全局指标验证通过。
- `kdocs_delivery.json`：云端文件定位及回读核验记录。

11 项单元测试通过；本地 37 页已实际渲染与检查，文本越界为零。没有修改既有公开聚合文件，没有提交、推送或部署网站。

云端 PDF 已核验完整 37 页。WPS 云端对部分中文字体使用替代字体，与本地 Noto Sans CJK 的字形不完全相同；保留实际云端截图用于核对，不声称跨平台像素一致。

方法解释、两套分类映射及局限见 [METHODS.md](METHODS.md)。

## 本机复现

以下命令复用本机已冻结源文件和压缩缓存，不重新扫描 citation graph。源路径与哈希保存在结果清单；迁移机器需要一起迁移清单引用的文件。不要把已有输出目录用于新定义，修改口径时另建版本目录。

```bash
PY=/home/ider/miniconda3/bin/python
PPTPY=/tmp/retraction-kdocs-20260916/venv/bin/python
CODE=research/disruption-ngd-2026-09
OUT=/mnt/hg02/openalex-snapshot/analysis/retraction-disruption-ngd/20260925

$PY -m unittest discover -s "$CODE" -p 'test_*.py' -q
$PY "$CODE/disruption_analysis.py" --stage all --output "$OUT"
$PY "$CODE/export_global_metrics.py" --output "$OUT"
$PY "$CODE/assemble_report.py" "$OUT"
$PY "$CODE/verify_results.py" "$OUT" --require-complete
$PPTPY "$CODE/export_tables.py" "$OUT"
$PPTPY "$CODE/build_deck.py" "$OUT/presentation.json" "$OUT/研究报告.pptx"
$PPTPY "$CODE/render_deck.py" "$OUT/研究报告.pptx" "$OUT/render"
```

NGD 初始研究表与控制表已分别冻结在 `ngd-ranked/` 和 `ngd-controls-final/`。如需从源重建，使用新目录：

```bash
$PY "$CODE/ngd_analysis.py" --output "$OUT/ngd-new"
$PY "$CODE/ngd_analysis.py" --controls-cohort "$OUT" \
  --initial "$OUT/ngd-new" --output "$OUT/ngd-controls-new"
```

原始图统计的正确性依赖前置 Disruption 项目验收。本研究的独立验收覆盖样本、原报告逐学科分子分母、来源与产物哈希、NGD 原始 pair、CD 聚合约束和图表数据绑定，不宣称再次独立计算全部引用图。
