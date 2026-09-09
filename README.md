# Retraction Observatory / 撤稿研究观测站

真实 Retraction Watch 数据驱动的静态研究网站；Python 标准库处理，浏览器按 gzip JSON 分片交互分析。支持撤稿年 / 发表年、学科、机构、作者、时滞、学科年度增长、全 / 分数计数、论文搜索和 CSV 导出。

**当前交付数据是 Retraction Watch 全文件 + OpenAlex 首 1000 DOI 的匹配子集。** 不应将 OpenAlex 子集解释为总体。运行下面的全量任务补齐所有有 DOI 的记录；无 DOI 部分依然保留于 RW 视图。详情见 `docs/RESEARCH.md`。

## 运行
Python >= 3.11，无第三方依赖。

```bash
# 使用交付的网站数据预览，不需要 API key
python -m http.server 8000 --directory dist
# 浏览器打开 http://localhost:8000

# 下载最新 CSV，并完整匹配 OpenAlex（可能耗时，推荐环境中设置 OPENALEX_API_KEY）
python pipeline/build.py --download --enrich --corpus all

# 只更新 Retraction Watch，不做 OpenAlex 匹配
python pipeline/build.py --download

# 从自己的 CSV 重建，不重新下载
python pipeline/build.py --rw /path/to/retraction_watch.csv --enrich --corpus all

# 仅作连通性与流程验证的部分匹配，不是研究样本
python pipeline/build.py --download --enrich --oa-limit 1000

python -m unittest discover -s tests
```

`--as-of YYYY-MM-DD` 限制已发生的通知日期，但不是历史数据库快照回放。无 `--enrich` 会生成无 OpenAlex 补充的新输出，并不会沿用上一版匹配。缓存按当日和语料隔离，同日中断后重跑可以恢复。

## GitHub 仓库
目标仓库为 `ider-zh/Scholarly-Retraction-Observatory`。首次上传命令：

```bash
git init
git add .
git commit -m "Add reproducible retraction research and dashboard"
git branch -M main
git remote add origin https://github.com/ider-zh/Scholarly-Retraction-Observatory.git
git push -u origin main
```

如果项目已经初始化了 git，就直接检查 remote 后添加目标远端；不要覆盖其他仓库。`data/raw` 与 `data/cache` 不进 Git；源文件 SHA-256 在清单中，正式研究应自行归档原文件。

GitHub Actions 工作流提供每周更新和手动运行，默认完整 DOI 匹配。可在仓库 Actions Secrets 配置 `OPENALEX_API_KEY`。任务失败会保持上次站点数据。自动更新通过 Pull Request 提交，合并后 Cloudflare 自动发布；仓库设置需要允许 Actions 创建 PR。首次刷新可能耗时，部分匹配仅用于调试。匿名 API 的预算可能不够覆盖完整同步。

## Cloudflare Pages
导入上述 GitHub 仓库，设置：

|配置|值|
|---|---|
|生产分支|`main`|
|框架预设|None|
|构建命令|`exit 0`|
|输出目录|`dist`|

网站本身不持有 API key；数据采集在 Python / GitHub Actions 执行。无需服务器数据库，更新数据后提交生成文件即可触发部署。JSON 分片保持单文件小于 Pages 静态文件上限。初次载入下载完整精简论文数据，后续可扩展为服务端查询 / 按需分片以减小移动端内存与流量。

Cloudflare 官方说明：https://developers.cloudflare.com/pages/framework-guides/deploy-anything/

## 目录
- `pipeline/build.py`: 下载、清洗、去重、OpenAlex 匹配、质量审计、生成分片。
- `dist/`: 可直接部署的静态网站和真实数据。
- `docs/RESEARCH.md`: 研究问题、公式、限制及下一阶段。
- `tests/`: DOI、通知筛选、去重、日期边界等统计正确性测试。
- `.github/workflows/refresh.yml`: 数据刷新与 PR。

数据归原来源的 CC0 条款；链接与署名保留。项目代码采用 MIT，详见 LICENSE。任何作者或机构数量都不是不端行为的认定。
