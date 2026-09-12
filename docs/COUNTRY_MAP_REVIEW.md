# 国家专题合并与离线地图

## 本轮调整

1. 删除 `ReportGuide.jsx` 中“为什么选 article？journal 类型的论文被排除了吗？”整段披露。没有删除数据范围标识或修改 article 筛选规则。
2. 国家旧比例专题与国家年度专题使用相同的 2000–2026 发表范围、OA 截止、机构国家归属和逐国 n/N。测试逐行核对两总体，旧版每万篇值只存在六位小数的发布舍入。重复入口不再出现在目录；旧 `country-rates` 专题与明确 `slice` 深链接保留，显示迁移入口。旧比例条形图改为可排名国家按值降序，小基数组不参与排名。
3. “国家内撤稿比例与年度趋势”增加离线地图/排序条形图切换。地图选择与现有国家年度图联动；总体、数量、百分比、每万篇三个指标共享已有数据和导出。

## 地图方法和边界

底图为 Natural Earth v5.1.2 的 1:110m admin-0 简化边界，采用 Natural Earth 1 投影，177 个本地 SVG 路径约 129 KB。输入摘要、公共领域条款和可复现生成方法见 `src/report/assets/README.md`。构建和浏览器运行无需下载底图，也不请求瓦片或外部 API。

- 底图只按 ISO_A2_EH 与已发布国家代码精确关联；不推断缺失代码，不重划或合并争议地区。边界仅作定位，不参与判断论文国家。
- 国家仍由论文的机构署名关联确定，不是作者国籍或责任。多国论文不能跨国相加；联合数据选择不是两库并集。
- 比例色阶只使用 n≥20、N≥1,000 的已发布单元；其他小基数用斜纹显示，真实数值仍可查看。无数据/不适用为灰色，计数的已观测零使用零色。
- 线性色阶随当前总体/指标更新，不按搜索或 Top N 重算；跨图同色不保证同值。条形图用于精确排序，地图用于空间分布。
- 54 个已发布国家/地区不在这份简化底图中，保留在选择器、条形图、完整表和导出；底图覆盖说明可展开查看。手机上很小的国家可使用选择器，而不是猜点位置。
- 原完整表和 CSV 复用 `CountryData`，切换地图/条形图不改变任何导出值；没有新增统计发布文件。

## 验证与证据

- 新增 `tests/snapshot-country-map.test.mjs`：旧/新专题范围及逐行 n/N 一致；目录合并和旧链接；可排名国家排序、原数据不变性；颜色状态、底图几何检查。
- `node --test tests/snapshot-*.test.mjs`：55 项通过。
- `npm test`：54 项 Python 测试通过。
- `npm run build`：通过；public/dist 数据均为 2,010,929 字节，36 条样本。保留原有大于 500 kB 的旧入口包警告。
- `scripts/check-country-map-browser.mjs`：三个指定尺寸、键盘选择、地图/条形图、两个总体×三个指标、CSV 一致性、合并入口、旧链接排序、专题弹层及 RW/OA 限制。浏览器拦截全部外部请求后地图仍正常；发现旧站全局 Google Fonts CSS 请求，保留在检查记录中并阻断，没有地图/瓦片/API 请求。本轮没有改动无关的旧站字体配置。实际结果见截图目录中的 `checks.json`。
- 最终地图浏览器检查 10 组通过；现有 `scripts/check-cohort-browser.mjs` 回归 9 组通过，包含国家/学科年度分母、各指标导出、来源切换和三个尺寸检查。无未捕获页面错误。截图完成后只修正测试对跨路由保留的图形/折叠状态以及旧站字体请求的预期，没有反复修改地图视觉。
- 实际 Chromium 截图目录 `/tmp/sro-geomap-review/`：`before-country-rates.png`、`before-countries.png`；`review-map.png`；`after/{desktop,tablet,mobile}-map.png` 与 `-full.png`；`confirmation/` 为脚本修正后的确认记录。已经打开审查旧率图、桌面地图及手机/平板地图。未检查 Firefox、Safari 或人工屏幕阅读器。

浏览器命令：

```bash
PLAYWRIGHT_MODULE=/tmp/snapshot-browser-check/node_modules/playwright/index.mjs \
CHROMIUM_PATH=/home/ider/.cache/ms-playwright/chromium-1169/chrome-linux/chrome \
AXE_PATH=/tmp/snapshot-browser-check/node_modules/axe-core/axe.min.js \
REPORT_QA_URL=http://127.0.0.1:5173/ \
REPORT_QA_OUT=/tmp/sro-geomap-review/confirmation \
node scripts/check-country-map-browser.mjs
```

本轮只编辑前端、依赖、地图资源/生成工具、测试和文档。工作区在任务期间另有公开数据从 `oa-2026-06-26-eb265b31c73b` 更新为 `oa-2026-06-26-7c6e5f2b98d6`（文件时间 2026-09-12 10:35），没有撤销或覆盖该更新；验收使用当前数据。任务初始 pipeline 文件校验值保持一致，不能将外部数据更新误称为本轮地图改造生成。未提交、推送或部署。
