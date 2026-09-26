# 近期离线研究交接

更新：2026-09-27，Asia/Shanghai。

## 当前状态

- `disruption/`：全库引用网络年度统计及双口径窗口缓存已完成；正式统计保持冻结，不接入网站构建。
- `taxonomy_ngd/`：全库 Concepts/Topics 共现距离、逐 Work membership、排名及数学切片已完成。
- `research/disruption-ngd-2026-09/`：复用两项资产，与既有 RW/OA 撤稿样本做探索研究；58页深色金山 PPT 已交付。
- 本轮提交包含此前尚未纳入 Git 的三个离线模块、代码、测试和说明。大数据、PPTX、PDF、截图仍在服务器外部目录，不提交到仓库。

## 专项交接

| 范围 | 交接入口 |
| --- | --- |
| Disruption 数据、窗口、性能和查询 | [disruption/HANDOFF.md](../disruption/HANDOFF.md) |
| NGD 数据、分类、性能和验收 | [taxonomy_ngd/HANDOFF.md](../taxonomy_ngd/HANDOFF.md) |
| 撤稿交叉研究、PPT、代码审计与下一步 | [research/disruption-ngd-2026-09/HANDOFF.md](../research/disruption-ngd-2026-09/HANDOFF.md) |

## 接手时注意

1. OpenAlex 为2026-06-26冻结快照，不能称为当前在线最新数据；RW为2026-09-10快照。
2. 当前PPT：https://www.kdocs.cn/l/cl717MhQQ4UJ ，58页。不要误更新早期37页或另一份外部编辑过的云文档。
3. 现有主统计复算一致，但研究层缓存来源绑定和自动验收覆盖仍有已确认缺口；见研究Handoff。未修复前不能把“通过”扩大解释成完整网络独立复算。
4. 不覆盖冻结结果目录，不把RW与OA相加，不将未定义指标填零；改定义另建结果版本。
5. 用户此次授权提交并推送GitHub；没有要求重新发布网站或更改公开聚合。后续操作按新的用户授权执行。

## 本次提交前实际检查

2026-09-27重新执行的本地检查（不是全库重算）：

- Disruption Python测试40项、独立reference测试14项通过。
- NGD核心测试7项、发布测试8项通过。
- 研究测试28项完成，其中1项因分析环境不含python-pptx跳过；PPT环境另跑4项通过。
- `disruption/engine` 的 `go test ./...` 通过（缓存结果）。
- `git diff --check`和待提交文件范围检查；不纳入正式数据、图片/PPT/PDF产物或凭据。
