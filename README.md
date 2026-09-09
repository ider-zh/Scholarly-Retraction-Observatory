# Scholarly Retraction Observatory

React + Vite + Recharts 构建的撤稿统计研究网站。**前端只发布预聚合统计结果、36 条以内的展示样本和研究说明，不下载或解压完整论文数据。**

## 架构

```text
Python 离线处理（原始 CSV / OpenAlex 缓存，仅本地或 Actions）
  → 清洗、原论文去重、日期检查
  → 年度趋势 / 学科 / 机构 / 作者 / 时滞 / 增长率 / 数据观察
  → public/data/report.json + public/data/samples.json
  → React 图表、分析说明、数据源与方法论
```

- `src/`：React 页面、图表组件和样式。
- `pipeline/build.py`：获取、清洗、匹配；完整记录保存在被 Git 忽略的 `data/processed/`。
- `pipeline/aggregate.py`：离线统计与有数值依据的观察文本生成。
- `public/data/report.json`：聚合统计；不含完整论文记录。
- `public/data/samples.json`：最多 36 条简化展示样本；不用于统计推断。
- `data/reference/openalex-audit.json`：带日期的独立数据源数量核查，不作为主统计总体。
- `docs/RESEARCH.md`：研究范围、公式、方法和限制。
- `scripts/check-public-data.mjs`：发布检查，拒绝 Gzip、CSV、Parquet、NDJSON 等数据文件；两份 JSON 总体积限制为 2 MiB。
- `dist/`：Vite 生成的可发布产物，不提交 Git。

## 开发与构建

Node.js >=22.12，Python >=3.11。

```bash
npm ci
npm run dev
npm run build
npm run preview
python -m unittest discover -s tests
```

普通前端构建仅使用仓库内已经生成的统计数据，不需要 Python、OpenAlex 密钥或重新下载数据。前端只对聚合后的时间序列进行展示筛选、后向三年均值和格式化，不进行论文级全库扫描。

## Cloudflare Pages

导入 `ider-zh/Scholarly-Retraction-Observatory`：

| 配置 | 值 |
|---|---|
| 生产分支 | `main` |
| 构建命令 | `npm run build` |
| 输出目录 | `dist` |
| Node 版本 | `22.16.0` 或更高支持版本 |

Cloudflare 会根据 package-lock.json 安装依赖；也可将命令设为 `npm ci && npm run build`。如使用环境变量指定 Node，设置 `NODE_VERSION=22.16.0`。旧版本的 `exit 0` 必须改为构建命令。

## 更新统计数据

```bash
# 可选交叉验证准备：匹配所有 DOI，不参与任何统计分析
# 推荐先在环境变量中配置 OPENALEX_API_KEY，不要写入前端或提交到 Git
python pipeline/build.py --download --enrich --corpus all

# 常规更新：仅使用 RW 主数据
python pipeline/build.py --download

# 调试用部分匹配：不是随机或代表性样本
python pipeline/build.py --download --enrich --oa-limit 1000

npm run build
```

GitHub Actions 每周和手动运行数据刷新：原始数据只在运行器内处理，更新 PR **仅提交 `public/data/`**。合并后 Cloudflare 构建新站点。常规刷新不调用 OpenAlex；可选交叉验证通过上述 CLI 单独执行。刷新失败不会提交不完整统计结果。

原始 CSV 和处理后全库均不属于网站资产，也不进入更新 PR。正式论文研究应自行把原文件和其哈希保存到专门的数据归档；Actions 不再上传完整原始数据附件。

## 图表与分析

1. 年度柱状图 + 后向三年均值，区分实际撤稿年与原论文发表年。
2. 撤稿时滞环图和学科分组条形图。
3. RW 官方前缀构成 7 个一级领域，130 个 Subject 构成二级标签；支持领域联动、数量分布、完整年度同比及学科 × 年份热力表。
4. 学科 P25 / 中位数 / P75 时滞对比及单学科趋势。
5. 机构和作者前列关联分布，支持全计数 / 分数计数，仅使用 RW 原始名称。
6. 每个主要图表附数据观察或读图解释，并分开呈现可能的解释与不能推出的结论。所有图表均可查看相应数据表。

统计 CSV 只导出图表聚合结果。样本搜索仅检索 36 条以内的展示样本，不提供全库论文下载。

## 重要范围说明

交付快照主总体是 RW 中 `RetractionNature=Retraction` 的记录，按原论文标识去重得到 **66,635** 篇。OpenAlex 已匹配 **998** 篇（查询字典序前 1000 个 DOI），这只是 DOI 匹配进度，并未完成逐条撤稿核验；所有统计图表均排除 OpenAlex 数据。

OpenAlex `is_retracted=true` 的 Work 记录可能包含撤稿通知；排除 `type:retraction` 后也仍可能包含被分为 article 的通知。本站不声称 66,635、135,236 或 97,729 是全球真实撤稿论文总数。恢复发表、更正等状态单列；主总体是当前 RW 文件的类别筛选结果，不是完整的历史事件重建。

数据源：[Retraction Watch / Crossref](https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/)、[OpenAlex](https://help.openalex.org/data/works/attributes/)。软件 MIT，来源数据按 CC0 条款。关联数量不等于研究不端责任认定。

## 从 v1 迁移

本次在当前分支删除了先前提交的 `dist/`、全部 Gzip 论文分片和旧的纯 JavaScript 页面，改为提交 React 源码与轻量聚合数据。Git 历史仍保留旧提交；此次没有强制改写历史。部署与正常前端使用不会再获取旧分片。后续克隆若仅需最新代码可使用 `git clone --depth 1`。
