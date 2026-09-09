# 撤稿研究方案与统计口径

## 研究问题
1. 每个日历年实际发生撤稿的原论文数量如何变化？与按发表年份回溯的撤稿队列分别绘图。
2. 哪些机构、作者与撤稿论文有关联？全计数与分数计数下分布是否改变？
3. 不同学科的撤稿数量、发表到撤稿时滞及完整年度的数量增长有何差别？
4. 数据缺失、身份消歧、跨学科归属和数据库覆盖如何影响上述比较？

## 数据与研究总体
主总体为下载的 Retraction Watch CSV 中 `RetractionNature=Retraction` 的原论文，截止快照日期。不是“OpenAlex 中所有 is_retracted=true 的记录”，也不是全球撤稿全集。Correction、Expression of concern、Reinstatement 不纳入撤稿通知计数。本研究是当前 CSV 中 Retraction 类别的原论文队列，不是完整历史事件重建。记录被改为恢复发表等其他类别时不会进入该队列，不能据此判断全部出版状态演变。

Retraction Watch: https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/
OpenAlex: https://help.openalex.org/data/works/attributes/
原始 CSV 来源: https://gitlab.com/crossref/retraction-watch-data

所有统计为描述性分析，不提供研究不端判定、机构绩效评分或因果结论。撤稿原因可能是诚实错误、编辑问题或其他原因；关联作者不必承担同等责任。

## 去重与数据字典

|字段|来源 / 计算|缺失或冲突处理|
|---|---|---|
|id|标准化 OriginalPaperDOI，次选 OriginalPaperPubMedID，最后 RW Record ID|不做标题模糊匹配；不同身份键的潜在同文可能未合并|
|retracted|RetractionDate|日期未知保留原论文但不进时间图；同文多通知取最早有效日期|
|published|OriginalPaperDate|同文日期冲突取最早有效日期，并计入质量审计|
|lag_days|retracted − published|负数排除于时滞统计，不删除论文；日期未知不插补|
|subjects|RW Subject 分号多标签|不混合进 OpenAlex 学科体系|
|institutions|RW Institution 原始字符串|可能包含院系、地址；不称作标准化大学排名|
|authors|RW Author 原始姓名|同名可能合并、异名可能拆分|
|rw_ids|所有关联 RW Record ID|用于追溯|

DOI 标准化移除 resolver URL / doi: 前缀、转小写并解码 URL。CSV 中缺失 DOI 的 unavailable 等字样不是 DOI。遇到同 DOI 多条 OpenAlex Work，以字典序最小 ID 作可复现选择并标记 duplicate_doi_match；需要后续结合 OpenAlex merge/redirect 表人工或规则审查。不同 DOI 的重复论文不在当前自动去重范围。

## 指标
- **原论文数量**：唯一论文键计数。一篇论文多个撤稿通知，论文数仍为 1。通知行数单独记录，源数据重复通知行尚不等价于唯一通知事件。
- **全计数**：每篇论文对每个不同作者 / 机构 / 学科贡献 1，因此分组合计可以超过论文总数。
- **分数计数**：论文在该维度有 k 个不同成员时，每个成员贡献 1/k。分母用论文原有完整成员列表，不因筛选而重新分配。未知成员不虚构；有成员的论文在该维度合计为 1。
- **时滞**：日期差（天）。展示年份为天数 / 365.25；P25/P50/P75 用排序样本的线性插值分位数。学科时滞是关联论文的未加权分位数，不随分数计数开关改变。
- **年度数量同比**：(R_t − R_(t−1)) / R_(t−1)。前期零时为 NA；前期小于 20 标记小基数。当前看板固定比较快照年前两个完整年，避免随年份筛选改变增长定义。少量缺报仍可能影响完整历史年份。
- **学科撤稿率（未实现）**：同一发表年 / 学科 / 作品类型 / corpus 的截至快照已撤稿论文数，除以该队列全部论文数。没有分母就不能叫撤稿率。不得用“当年撤稿数 / 当年发表数”冒充队列撤稿概率。

趋势图默认展示 2000 到快照年，可切换展示范围。所有快照指标与机构 / 作者排名固定使用完整队列范围，不跟随趋势图筛选。学科页面可切换一级／二级，并筛选所属领域。全部图表仅使用 RW；OpenAlex 仅在数据说明中显示交叉验证进度，不进入分类、排序或推断。

## 数据质量与复现
- 清单保存原始 CSV SHA-256、生成时间、截止日期、源 URL、语料范围、匹配尝试数和命中数。
- 完整数据仅保存在本地或 Actions 运行器的 data/processed。网站只发布 report.json 聚合统计和最多 36 条 samples.json 展示样本；采集失败不覆盖已发布站点。
- OpenAlex 按原论文 DOI 批量查询，50 DOI / 请求；key 仅由环境变量提供。缓存按日期和 corpus 隔离；恢复同日任务复用缓存，跨日重新请求。
- `--oa-limit 0` 全 DOI 匹配；正整数只取字典序前 N 个 DOI，是调试子集，不是随机样本。偏倚明显，不能用该子集声称总体学科 / 机构 / 作者分布。
- 匹配尝试与命中数仅在数据与方法页展示，DOI 命中不等于撤稿状态已验证；无 DOI 论文仍保留于 RW 总体。
- API 是实时的；一次较长采集期间可能变化。CSV 下载亦未锁定 Git commit，只能用保存原文件的哈希复现该版本。正式发布研究时应保存原始文件和数据来源提交版本到独立归档。
- 作者 / 机构匹配覆盖不是准确率。人工审计可按国家、学科、年份分层抽样核查 DOI、身份和日期。

## 下一阶段：标准化比较与推断
需要另采全部论文分母，才能实现发表队列撤稿率和跨学科标准化比较。建议先设固定作品类型（article / review 分开）、corpus、发表年代和观察期，例如发表后 5 年撤稿比例；不足 5 年随访的队列不直接比较。

生存分析需要加入未撤稿论文与观察截止日期，作为右删失样本；不能只拿撤稿数据库画 Kaplan–Meier 后解释为总体风险。进一步可做累计发生率、学科分层与年份控制，但应先审查匹配及选择偏差。

建议后续研究：撤稿原因多标签分布、期刊 / 出版商批量撤稿事件、国家合作结构、撤稿前后引用、机构规模标准化、恢复发表事件。这些需要新的数据口径与验证，不在当前页面中伪装成已完成结果。

## React 前端发布边界（v2）

统计结果由 pipeline/aggregate.py 离线生成：年度数量、学科时间序列、时滞分位数、直方图、同比，以及机构 / 作者全计数和分数计数前 20。前端默认展示其中前 15 个机构 / 作者。未发布其余姓名或论文级数据。

样本按原论文 ID 的 SHA-256 排序取前 36 条，保留简化书目信息和日期，仅供解释字段。它们不用于图表计算或代表性推断。网站搜索只覆盖这些展示样本。统计 CSV 仅包含图表数据。

时间趋势的后向三年均值使用当前完整年及之前两年的数量，首两个年度和未完整年度不显示均值。年度缺口补零。学科同比固定采用全计数，基期不足 20 篇不进入排序。时滞比较图按关联数量选取有效样本至少 20 篇的前 8 个学科。

每个主要图表包含数值观察、读图解释或方法注释。pipeline 的观察句使用可检查的统计量生成；可能的原因与不能推导的结论单独显示，不提供未经验证的因果解释。年度峰值不等同于不端发生率峰值；原始名称关联数量不等于个人责任。

独立 OpenAlex 数量核查保存在 data/reference/openalex-audit.json 并标注核查日期，网站只将其作为数据源差异介绍。它不会被混入 RW 主分析总体，也不声称已经完成全量对账。

构建检查只允许 public/data 中存在 report.json 与 samples.json，限制样本最多 36 条、两份统计文件合计小于 2 MiB；拒绝发布 gzip、csv、parquet、ndjson 等数据资产。GitHub 更新工作流只提交聚合结果，不上传完整原始数据附件。

## 两级学科体系与来源背景

Retraction Watch 由 Ivan Oransky 与 Adam Marcus 于 2010 年创办，由美国非营利组织 Center for Scientific Integrity 支持。2023 年 9 月 Crossref 收购其数据库，RW 团队继续维护；新闻业务保持独立。详细背景及官方出处保存在 `data/reference/rw-background.json`，随聚合结果发布到网站。

分类沿用 [RW 官方 Subject 前缀](https://retractionwatch.com/retraction-watch-database-user-guide/retraction-watch-database-user-guide-appendix-a-fields/)，不由 OpenAlex 推定：

|一级前缀|中文展示|官方名称|
|---|---|---|
|B/T|商业与技术|Business and Technology|
|BLS|基础生命科学|Basic Life Sciences|
|ENV|环境科学|Environmental Sciences|
|HSC|健康科学|Health Sciences|
|HUM|人文学科|Humanities|
|PHY|物理科学|Physical Sciences|
|SOC|社会科学|Social Sciences|

二级保留完整 Subject 标签作为 ID，例如 `(HSC) Medicine - Cardiology`。连字符不继续拆层；不同前缀下的同名学科保留独立身份。当前快照共有 130 个二级标签，该数量随来源更新变化。缺失或无法识别的前缀纳入 UNKNOWN，并保留原始标签。

一级先将每篇论文的前缀去重，所以同一论文命中某领域两个二级学科时，该一级仍只计 1。跨领域合计仍可能超过论文总数。分数计数在两层分别使用该论文的不同成员数：一级 1/k₁，二级 1/k₂。筛选父领域不重新归一化，子学科分数之和不必等于父领域分数。例：一篇论文属于 HSC 两个标签与 BLS 一个标签，一级分别贡献 1/2，三个二级各贡献 1/3。

`pipeline/aggregate.py` 不读取 `oa` 字段生成任何统计维度；输入 OA 匹配结果的变化不改变 RW 统计。全量跨源核验尚未完成。当前 1,000 次 DOI 查询、998 个匹配不是核验准确率，也不是代表性抽样。

发布的分数计数保留三位小数，汇总时可能存在舍入误差。
