# 2026 年 9 月 Kdocs 研究报告制作过程

本目录归档撤稿学科专题的分析、PPT 制作、综述写作、核查和 Kdocs 更新代码。它是实际制作过程的源码记录，不是新的生产分析流水线，也不是可以从空目录一键重建所有版本的工具。

## 范围与安全

- 未提交原始快照、逐篇匹配数据、云端响应日志、签名下载地址、认证信息、虚拟环境、PPT/Word/PDF 和截图。
- 不改变 `pipeline/`、网站代码、公开聚合文件或现有统计规则。
- `scripts/` 中归档脚本保留原有绝对路径、云文档 ID、阶段性断言和依赖关系，用于追踪制作过程。**不要批量执行或导入这些脚本**：其中一些在顶层运行，并会创建、替换或分享真实云文档。
- `cloud.py`、`*publish*.py`、`publish_*.py`、`update_page27.py`、`patch_page27.py`、`expand_sample_paragraph.py` 涉及云端操作。重新使用前必须审核目标 ID、当前版本、覆盖授权及权限；凭据仅由 `kdocs-cli` 管理。
- `eligibility_audit.py` 是单独整理的只读复核入口，只读取本地已完成分析的数据，不调用云端、不修改数据、不扫描下载新快照。

## 制作阶段

| 阶段 | 脚本 | 作用 |
| --- | --- | --- |
| 发表年份分析 | `extract.py`、`build_deck.py`、`validate.py` | 检查公开聚合，制作初版图表与 PPT，检查图形边界及渲染 |
| 初版发布及局部修订 | `cloud.py`、`update_page27.py`、`patch_page27.py`、`merge_audit_revision.py` | 云文档操作、局部页面更新及审查结果合并 |
| 撤稿年份分析 | `event_analysis.py`、`event_deck.py`、`event_verify.py`、`event_publish.py` | 从 RW 日期选取样本、按 OA 分类统计、独立 SQL 复核及发布 |
| 两种时间口径分章 | `name_time_views.py`、`refactor_time_chapters.py` | 区分撤稿记录年与发表年队列，重排章节 |
| 研究简报 | `nick_data.py`、`nick_build.py`、`nick_publish.py` | 形成匹配样本正文和纯 OA 附录，生成 PPT 与 Word |
| 主类内二级分析 | `nick_refine.py`、`nick_refine_publish.py` | 先取前三主学科，再在各组中选二级标签／子学科，补充公式 |
| 文章版综述 | `neutral_article.py`、`publish_article.py`、`publish_neutral.py` | 科普叙事稿、中性综述及新文档发布 |
| 深色 PPT | `dark_audit.py`、`dark_deck.py`、`publish_dark.py` | 核查总体及分类实体数量、定位缺失个案、重绘 14 张图表并更新 19 页 PPT |
| 样本过程说明 | `expand_sample_paragraph.py`、`eligibility_audit.py` | 解释匹配规则、23 条排除记录、RW 日期及样本边界 |

`manuscripts/` 保存两篇文章初始源稿及最后一次样本过程扩写。中性综述的云端修订仅替换指定段落，完整修订文档不在此重复保存。

## 方法与复核结果

使用已验收的 OA **2026-06-26** 与 RW **2026-09-10** 快照，不宣称是执行归档时的最新在线数据库。

1. RW 按原文身份整理后为 66,700 条。使用规范化后的原文 DOI／PMID 精确匹配；候选不唯一、标识符或身份存在冲突时不强行选取。
2. 60,313 条 RW 记录唯一匹配到 **60,311 个不同 OA Work**。未匹配 5,502 条、冲突 863 条、歧义 22 条，四类合计 66,700。
3. 在不同 Work 中，22 条位于 expansion，1 条缺少发表年份；按共同资格范围保留 **60,288 条**。该步骤不限定 article，也不要求 OA 撤稿标记为真。
4. 按每个 Work 最早可解析的 **RW RetractionDate** 归年，排除 2000 年前的 458 条及 2025 年后的 1,485 条，最终为 **58,345 条**。
5. Concepts 保留已有多标签；L1 计该标签全体文献，不与父 L0 取交集。Topics 使用 `primary_topic` 路径。年度占比分母是当年全部合格匹配撤稿文献，包含分类缺失项。
6. 纯 OA 附录另按发表年份和同学科全部合格发文计算标记比例，不与正文混用。

深色版补充核查：全部 Work 510,372,821 条，撤稿标记 115,627 条；core 分别为 317,820,190 与 114,538。RW 原始表有 72,476 行，其中 Retraction 66,869 行，不能将行数直接当作去重论文数。Concepts 实体 65,026 个，L0 19 个、L1 284 个；Topics 路径为 4 Domain、26 Field、252 Subfield、4,516 Topic。

正文 L0 唯一缺失个案为 `W4210257207`，本地 `concepts=[]`，RW 撤稿日期为 2022-02-01。保留在总分母中，没有依据题名或 Topics 回填标签，也未将缺失归因于某个未经核实的原因。

## 环境与依赖

`requirements.txt` 记录制作环境实际安装的 Python 包版本，不表示已经在全新环境完成可移植性验证。另需 LibreOffice（本地排版检查）、Noto CJK 字体，以及经用户授权并认证的 `kdocs-cli` 2.6.15（仅云端操作需要）。

历史工作目录：

- `/tmp/retraction-kdocs-20260916`：初版、发表队列、撤稿年份及脚本。
- `/tmp/retraction-nick-20260920`：简报、文章、样本聚合、云端验证。
- `/tmp/retraction-nick-20260920-v1`：早期 15 页版本备份，供重排脚本读取。
- `/tmp/retraction-dark-20260921`：目前 19 页深色版及审计。
- `/mnt/hg02/openalex-snapshot`：本地快照及分析产物。

历史脚本还依赖未入库的 `published.json`、`analysis.json`、`all-subjects.csv`、早期 PPT 及备份。`published.json` 是当时解码后的报告对象，不是简单重命名某个现有 JSON。重新制作时应先恢复对应输入和阶段版本，再调整路径；不要直接将历史发布脚本当作当前发布入口。

### 只读核查

在已安装 DuckDB 且本地快照分析目录存在的环境中，从仓库根目录运行：

```bash
python research/kdocs-2026-09/eligibility_audit.py \
  --snapshot-root /mnt/hg02/openalex-snapshot \
  --manifest public/data/snapshot/manifest.json
```

默认 32 个 DuckDB 线程、128GB 内存上限；可用 `--threads`、`--memory-limit` 调整。输出汇总，不输出逐篇身份数据。

语法核查无需导入或运行历史脚本：

```bash
python -c "import ast,pathlib; paths=list(pathlib.Path('research/kdocs-2026-09').rglob('*.py')); [ast.parse(p.read_text(), filename=str(p)) for p in paths]; print(len(paths), 'Python files parsed')"
```

## 历史验证注意事项

- 30／37／38／15／19 页的断言分别针对不同历史版本，不能全部用最终 PPT 运行。
- Kdocs 的写入响应不代表读取端立即同步。最后的段落替换第一次回读仍是旧内容，随后回读确认五段新文完整，正文其他部分不变；`expand_sample_paragraph.py` 保留了首次校验逻辑，需要结合这个延迟事实理解。
- 文章读取返回过仅提示高级格式需 `otl.block_query` 的 warning；正文逐段比对完整。`publish_article.py` 中“不允许任何 warning”的历史断言因此触发，之后另行完成了正文校验，不应解读为未创建文档。
- `source-manifest.json` 用于核对归档来源和源码内容；不包含云端导出 URL 或认证信息。

目前交付：[19 页 PPT](https://www.kdocs.cn/l/csRG5lIKtpsS)、[叙事综述](https://www.kdocs.cn/l/cpeKwZKhEVVz)、[中性方法与结果综述](https://www.kdocs.cn/l/cgrIJBxx1mWs)。公开链接不是发布凭据。
