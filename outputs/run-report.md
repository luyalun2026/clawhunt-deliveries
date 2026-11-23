# 运行报告（自动生成）

- 生成时间：2026-11-23T21:48:39
- 命令：`python verify.py`（内部 `pytest tests -q`）
- pytest 汇总：`17 passed in 0.96s`；退出码 0
- 用例 17，通过 17，失败 0，跳过 0
- 差异 CSV 行数（inconsistent 夹具）：5
- 差异类型：contract_space_not_leased, expired_contract_room_leased, leased_without_contract, occupancy_mismatch, seat_sum_mismatch

## 用例 × 结果矩阵

| 验收分组 | 用例数 | 通过 | 失败 |
|---|---|---|---|
| AC1 四类差异检出 | 2 | 2 | 0 |
| AC2 一致时退出 0 且仅表头 | 1 | 1 | 0 |
| AC3 只发 GET | 6 | 6 | 0 |
| AC4 出租率重算对拍 | 2 | 2 | 0 |
| 边界 5 例 + CLI | 6 | 6 | 0 |
| **合计** | **17** | **17** | **0** |

## 口径说明

- 用例数与通过率由 junit.xml 解析得到，未人工填写。
- 出租率按基点（bp）整数比较，容差 50bp；重算口径为「已租工位数 ÷ 可租工位数」。
- 只读性由 `ReadOnlyClient` 结构性保证（写方法直接 raise），并由用例断言调用方法集 ⊆ {GET}。
