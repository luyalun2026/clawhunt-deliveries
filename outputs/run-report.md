# 运行报告（自动生成）

- 生成时间：2026-11-24T19:58:46
- 命令：`python verify.py`（内部 `pytest tests -q` + `python probe.py`）
- pytest 汇总：`26 passed in 3.99s`；退出码 0
- 用例 26，通过 26，失败 0

## 用例 × 结果矩阵

| 验收分组 | 用例数 | 通过 | 失败 | 结论 |
|---|---|---|---|---|
| AC1 20 轮并发每轮仅一单 accepted | 2 | 2 | 0 | 通过 |
| AC2 到期释放后新的报备被 accepted | 4 | 4 | 0 | 通过 |
| AC3 四类拒绝与 reason code 正确 | 9 | 9 | 0 | 通过 |
| AC4 重复拒绝不含首单报备方身份 | 2 | 2 | 0 | 通过 |
| 其他（边界与加固） | 9 | 9 | 0 | 通过 |
| **合计** | **26** | **26** | **0** | **全部通过** |

## 实测指标（probe.py 运行期提取）

- `concurrency_rounds` = `20`
- `accepted_wins` = `20`
- `duplicate_losers` = `20`
- `unexpected_results` = `0`
- `round_ms_max` = `37.8`
- `round_ms_avg` = `22.7`
- `eight_way_winners` = `1`
- `eight_way_duplicates` = `7`
- `keys_before_expiry` = `3`
- `keys_after_expiry` = `0`
- `expired_count` = `1`
- `reentry_status` = `accepted`
- `identity_leaks` = `[]`
- `first_rule_version` = `v1`
- `first_protection_until` = `2027-02-13T10:00:00Z`

## 口径说明

- 用例数与通过率由 junit.xml 解析得到，未人工填写。
- 指标由 probe.py 在真实执行路径中采集，写入 outputs/metrics.json 后并入本报告。
- 并发由真实多线程 + 真实 SQLite（WAL、BEGIN IMMEDIATE、部分唯一索引）验证，不是模拟。
- DDL 与 PostgreSQL 16 兼容；生产把 connect() 换成 psycopg 即可，部分唯一索引语义一致。
- 保护期天数、延长天数与最大延长次数全部从受理时锁定的规则版本读取。
