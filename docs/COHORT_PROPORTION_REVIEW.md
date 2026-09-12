# 学科内、国家内撤稿比例与发表队列趋势

## 范围与口径

本轮按用户的新增统计请求实施，不是为了视觉重设计改写统计。只修改本地工作树和本地站点聚合资产；未提交、推送或部署。

- 本地检查 URL：`http://127.0.0.1:4173/`；基线提交 `767ed56`，包含此前尚未提交的报告 UI 工作。
- 本地新聚合版本：`oa-2026-06-26-eb265b31c73b`。OpenAlex 快照截止 `2026-06-26`；RW 记录截止 `2026-09-10`。
- Topics / Concepts 沿用 `fields.json.discipline_explorer` 的全部主、子层节点和已有分子/分母。未修改分类标签、父子关系或原统计。
- 国家新增 `geography.json.country_explorer`，227 个国家/地区、2000–2026 年；只采用机构所在国，不是作者国籍、署名地址国家或合作国家对。

对某节点或国家 g、某发表年 y，图中百分比为：

`P(g,y) = 截至观察截止日已被记录撤稿且属于 g、发表于 y 的合格论文 n / 属于 g、发表于 y 的全部合格论文 N × 100%`

这是同学科/同国**发表论文中的已观测撤稿比例**，不是该学科/国家在全部撤稿样本中的占比。每个年度点使用自己的年度分母，不沿用全历史分母。保留原 `share`（样本内覆盖）和 `rate`（每万篇）指标；新增 `proportion` 只是明确以百分比表达同口径 n/N。

时间轴是**原论文发表年，不是撤稿事件年**。OpenAlex 标记没有本分析所需的逐条撤稿事件日期；不能用某年发生撤稿的论文除以该年发表论文。近期发表队列的观察期更短，末年不完整；图不是最终撤稿风险或因果趋势。Concepts 仍是历史旧标签，不能解释为当前学科分类随时间的演进。

支持两个研究总体：

- `A1`：主体库 article 中通过原论文身份与日期筛选的 OA 撤稿标记论文；分母沿用 D 的筛选规则。
- `C_D`：截至 OA 快照日前已由 RW 记录撤稿、成功匹配 OA 且通过相同筛选的原论文。不是全部 RW，也不是 RW+OA 的并集；只在联合选择时可用。

RW 单库没有兼容全体发文分母；Subjects 不提供学科内比例，也不挪用 OA 分母代替。N=0 的比例未定义，不显示观测零；n≥20 且 N≥1,000 才参与比例排名。国家/Concepts 可多标签关联，不能跨节点加总。同篇同国去重，缺少机构国家的论文单列，不重新分配。

## 数据补算与契约

`pipeline/country_analysis.py` 从已有角色筛选后的维度缓存读取机构国家 × article × 发表年发文量，从已验证的 A1/C_D 身份集合生成对应年度 n。没有重新下载或全量扫描快照，也没有修改来源 run 的扫描缓存。

国家数组编码为 `[2000 年起总计, 2000, 2001, …, 2026]`，包括两总体的计数、共享同口径分母及国家缺失组。它与学科数组的全历史首项不同，因此方法和导出均显式标注年份范围。

报告生成器新增可选 `--output-dir`，本次隔离构建到 `data/processed/country-trends-20260911/report`；匹配与引用派生文件也写入隔离目录。构建后通过 `pipeline.publish_snapshot` 的校验与原子替换安装到本地 `public/data/snapshot`，这不是远程部署。

生成和浏览器校验包括：年度 n≤N、数组首项等于逐年求和、非负安全整数、同一快照/研究总体/国家口径、扫描代码与配置哈希；国家年度和必须复现已有两组 G1 国家队列的 n/N。无可用国家维度时不声明此能力。

新国家统计代码与报告生成器源码哈希纳入 release ID，manifest 新增 `country_explorer` 能力与年度和质量门槛。因版本和文件哈希更新，9 个章节聚合文件均重写。除 release ID 和既有非确定性数组排列顺序外，**全部 109 个旧图表的完整内容及旧学科统计均一致**；不是只比较总数。公开数据现在为 1,964,438 bytes，仍小于 2 MiB，并保留原 36 个展示样本；没有加入原始论文、署名或引用边。

## 页面与链接

- Topics / Concepts 正文显眼位置提供数量、学科内比例、样本覆盖、每万篇切换，分布图与年度图、解释、完整数据表及 CSV 联动；主/子节点继续用原树索引。
- 地理正文增加国家内比例、数量与每万篇切换、国家检索与趋势选择；国家分布条形可直接联动到该国年度图。
- 新“国家内比例与年度趋势”专题支持弹层与独立页；弹层切换不覆盖正文，关闭后恢复焦点。原 G1/G2/G3 入口和全部旧 slice 链接保留。
- 百分比图仍以零为基线，上限按实际最大值绘制，避免小于 1% 的曲线和条形被压扁；不修改数值。年度横轴明确写“原论文发表年”。

示例：

```text
#/snapshot/topics?sources=oa&metric=proportion
#/snapshot/concepts?sources=oa&metric=proportion
#/snapshot/geography?sources=oa&node=CN&metric=proportion
#/snapshot/geography/topic/countries?sources=rw%2Coa&population=C_D&node=CN&metric=proportion
```

复用现有 `sources`、`node`、`parent`、`population`、`metric` 查询键，不新增全局视图状态。年度 CSV 保留逐点 n/N、原始精度、年份、指标、总体、截止日与来源哈希，未用图中 Top N 或缩放范围裁剪导出。

## 检查与截图

实际命令及证据保存在 `/tmp/sro-cohort-review/`：

- `npm test`：54 个 Python 测试通过；新增缺失国家维度、跨国去重、按年分母和 n>N 拒绝测试。
- `node --test tests/snapshot-*.test.mjs`：45 项通过，包括所有学科节点逐年比例、国家年度与原 G1 两组共 454 单元复核、缺失与零、版本与分母篡改拒绝、小比例图尺度。
- `npm run build`：构建及 public/dist 聚合校验通过，日志 `build.log`。
- `scripts/check-topics-browser.mjs`：26 组通过；109 个专题 CSV 与 109 个旧章节深链接，日志 `topics.log`。
- 新 `scripts/check-cohort-browser.mjs`：9 组通过，检查两层节点、两总体、多指标、国家切换、年度 CSV、来源禁用、弹层独立状态、三个视口和 axe。最终结果见 `final/checks.json`。
- 更新原章节回归识别新增国家入口；44 组通过，106 个非概览切片 CSV 核对通过，最终结果见 `chapter-final/checks.json`。

实际使用项目已有 Playwright 库、Chromium 136.0.7103.25 和 axe；未声称安装或调用缺失的浏览器 skill。视口为 1440×900、768×1024、390×844。

另以 CSS zoom 200% 做等效内容放大检查，三个章节均无全局横向溢出，见 `final/zoom-checks.json` 和 `zoom-*.png`；这不冒充浏览器原生缩放测试。已实际查看桌面 Concepts 曲线、平板国家曲线、手机国家曲线与 Topics 分布、平板 Concepts 指标区域、桌面国家选择器及放大后的国家控件截图。

初审截图 `review/*-time.png` 发现比例图被原 1 单位纵轴下限压扁；首次验收 `confirmation/mobile-geography-metrics.png` 检出国家选择器溢出。集中修复纵轴与选择器布局后，确认截图保存在 `final/`，包含各视口的 `*-metrics.png`、`*-distribution.png`、`*-time.png`、完整页面和国家弹层。浏览器脚本的两个初始断言问题（非唯一标题定位及 option 的 disabled 检查）亦修正，不把这些失败报告为功能通过。

## 限制

本轮只检查本地 Chromium，未验证部署站点、Safari 或 Firefox。保留已接受的回溯验证来源缺口，不补造下载前 manifest/传输时间。旧 RW 入口 bundle 超过 500 kB 的既有构建提示未处理。国家合作对仍是既有描述性关联分析，没有把单国分母套在合作对上；撤稿事件年发生率、最终撤稿风险均未计算。
