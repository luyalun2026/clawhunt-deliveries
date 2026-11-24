# 运行报告（自动生成）

- 生成时间：2026-11-24T20:42:14
- 命令：`python verify.py`（内部 `pytest tests -q` + `python probe.py`）
- pytest 汇总：`53 passed in 3.67s`；退出码 0
- 用例 53，通过 53，失败 0

## 用例 × 结果矩阵

| 验收分组 | 用例数 | 通过 | 失败 | 结论 |
|---|---|---|---|---|
| AC1 12 场景各有期望行为、执行脚本、实际结果三栏 | 15 | 15 | 0 | 通过 |
| AC2 5 个汇总查询结果等于各会所单独查询之和 | 8 | 8 | 0 | 通过 |
| AC3 所有不一致场景都有问题单（含涉及表/接口/建议改法） | 3 | 3 | 0 | 通过 |
| 边界与加固：唯一企业/私有活动/停业只读/字典/导出/回落/软删/隔离 | 8 | 8 | 0 | 通过 |
| AC2-SQL 5 条汇总 SQL 在真实引擎执行并对拍（含非恒等式校验） | 19 | 19 | 0 | 通过 |
| **合计** | **53** | **53** | **0** | **全部通过** |

## 实测指标（probe.py 运行期提取）

- `engine` = `postgresql`
- `server_version` = `16.4`
- `scenarios_total` = `12`
- `scenarios_consistent` = `12`
- `issues` = `0`
- `sql_engine` = `postgresql`
- `sql_all_passed` = `True`
- `aggregate_max_diff` = `0`

## 口径说明

- 用例数与通过率由 junit.xml 解析得到，未人工填写。
- 指标由 probe.py 在真实执行路径中采集，写入 outputs/metrics.json 后并入本报告。
- SQL 对拍由 tools/run_sql.py 在真实 SQL 引擎执行 5 条汇总 + 5×N 条分会所 SQL，结果写入 outputs/sql_results.json（引擎=postgresql，全部通过=True）。
- 12 个场景本轮全部一致（0 条问题单）；test_09/test_10 用注入不一致的方式验证「出单」通路本身有效，不是空跑。
- 在驻企业数按「企业-会所入驻关系」计数（同一企业双会所计 2），另单列 distinct_enterprises 作为口径说明，不参与求和断言。
- SOP 完成率对拍用「分子分母求和」与「按会所样本量加权平均」两条独立路径比较，二者必须相等。
- 全部数据为虚构生成，不含任何真实个人信息或企业信息。
- 返工整改（v3）：12 个场景改为 sql/scenarios/S01~S12.sql 逐份真实 SQL / 接口桩执行（PL/pgSQL 函数见 sql/00_api_pg.sql，读写 contact/opportunity/event_registration/referral 等真实表），app/ 下内存模型已删除；5+5 汇总 SQL 与 12 场景均在 PostgreSQL 16.4 上实跑（engine=postgresql）；S03 联系人真实跨会所（S1→S2）、S05 以 A/B 会所身份走 api_read_opportunity_as_site 断言字段集合；ISSUES.md 增补执行环境（库版本/表结构/接口桩/隔离方式）。
