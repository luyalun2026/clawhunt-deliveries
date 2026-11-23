# 运行报告（自动生成）

- 生成时间：2026-11-23T22:40:17
- 命令：`python verify.py`（内部 `pytest tests -q` + `python probe.py`）
- pytest 汇总：`67 passed in 38.68s`；退出码 0
- 用例 67，通过 67，失败 0，跳过 0（跳过项为需本机安装 Playwright 浏览器的页面层用例）

## 用例 × 结果矩阵

| 验收分组 | 用例数 | 通过 | 失败 | 跳过 | 结论 |
|---|---|---|---|---|---|
| AC1 A 的线索列表接口恰好返回 8 条 | 3 | 3 | 0 | 0 | 通过 |
| AC2 6 类越权访问全部被拒（状态码断言） | 11 | 11 | 0 | 0 | 通过 |
| AC3 A 导出的线索文件行数为 8 | 3 | 3 | 0 | 0 | 通过 |
| AC4 审计记录条数等于越权尝试次数 | 6 | 6 | 0 | 0 | 通过 |
| 边界与加固：主管 13 条/站点隔离/URL 变体/未认证/双向越权/软删除/矩阵完整 | 6 | 6 | 0 | 0 | 通过 |
| 其他（边界与加固） | 38 | 38 | 0 | 0 | 通过 |
| **合计** | **67** | **67** | **0** | **0** | **无失败** |

## 实测指标（probe.py 运行期提取）

- `cells_total` = `80`
- `cells_consistent` = `80`
- `cells_mismatch` = `0`
- `denials_expected` = `42`
- `audit_denied_records` = `42`
- `list_totals` = `{"A": {"status": 200, "total": 8}, "B": {"status": 200, "total": 8}, "supervisor": {"status": 200, "total": 13}, "site_lead": {"status": 200, "total": 13}}`
- `export_rows` = `{"A": 8, "B": 8}`
- `export_leaks` = `{"A_has_B": false, "B_has_A": false}`
- `search_cross_tenant_hits` = `{"A_searches_B": 0, "B_searches_A": 0}`

## 口径说明

- 用例数与通过率由 junit.xml 解析得到，未人工填写。
- 指标由 probe.py 在真实执行路径中采集，写入 outputs/metrics.json 后并入本报告。
- 线索 id 的编号：test_16b 也归入 AC4 组（矩阵 allow 单元格全通过）。
- matrix.json 由 _gen_matrix.py 按声明式规则生成（不调用被测系统），用例反向校验实现，避免自证。
- 不存在 id 与不可见 id 返回完全相同的 404 体，防止存在性侧信道。
- 全部企业名、联系人、金额均为虚构数据。
