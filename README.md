# #2442 共享数据与会所级数据边界验证 — 交付包（v3 · PostgreSQL 16 真实执行版）

**一句话**：12 个场景与 5+5 汇总 SQL 全部在 **PostgreSQL 16.4** 上用真实 SQL / 接口桩执行，
矩阵里没有一个数字是手写的；`app/` 下已不存在任何内存模型。

## 一键复跑（三步）
```bash
# 1) 准备一个空库（本单约定 PostgreSQL 16）
export DATABASE_URL=postgresql://user:pass@host:5432/your_db

# 2) 5+5 汇总 SQL 对拍 → outputs/sql_results.json（engine 应为 postgresql）
python tools/run_sql.py

# 3) 12 个场景逐个执行 → outputs/scenarios.json / outputs/matrix-full.md
python tools/run_matrix.py

# 4) 全量用例 + 验收报告
python verify.py
```
未设置 `DATABASE_URL` 时：`tests` 自动降级为「读随包交付的 PG 结果 + 校验场景脚本 sha256 未被改动」，
`tools/run_sql.py` 改用 SQLite 3 复跑同一批 SQL 并与 PG 产物逐项比对（不覆盖 PG 产物）。

## 最新运行结果（2026-11-24，本机 PostgreSQL 16.4）
- `python -m pytest tests -q` → **53 passed**，0 failed；5 个验收分组全绿
  （AC1 15/15、AC2 8/8、AC3 3/3、边界与加固 8/8、AC2-SQL 19/19）。
- `tools/run_sql.py` → `outputs/sql_results.json` 的 `engine = postgresql`，5/5 指标 `passed`，
  `diff` 全为 0，`filters_effective` 全为 true。
- `tools/run_matrix.py` → 12/12 场景 `ok=true`，引擎 PostgreSQL 16.4（见 `outputs/matrix-full.md`）。
- 生成时间与逐项数字见 `outputs/verify.json`（不手写）。

## 本轮返工整改对照（针对 v2 审核意见的 5 条）
| # | 审核意见 | v2 状态 | v3 整改 | 证据 |
|---|---|---|---|---|
| 1 | [blocker] 12 个场景仍跑在自写的内存模型上，`执行脚本` 栏全是 `app/scenarios.py::scenario_Sxx` | 未改 | **删除 `app/scenarios.py` / `app/aggregates.py`**；每个场景改为一份 `sql/scenarios/Sxx.sql`，内容是真实 SQL 或 PL/pgSQL 接口桩调用，最后一行把「期望/实际/是否通过」写入 `scenario_result` 表；矩阵「执行脚本」列直接指向该 SQL 文件 + sha256 | `outputs/matrix-full.md`；`test_03_ac1_matrix_matches_script_hashes`（脚本改动但结果未重跑 → 用例红） |
| 2 | [major] 执行引擎是 SQLite，不是约定的 PostgreSQL 16 | 未改 | 本机部署 PostgreSQL 16.4（便携版，`initdb` + `pg_ctl -p 55432`），`DATABASE_URL=postgresql://postgres@127.0.0.1:55432/ch2442` 实跑；`sql_results.json` 与 `scenarios.json` 的 `engine` 均为 `postgresql`，并记录 `SELECT version()` = `PostgreSQL 16.4` | `outputs/sql_report.md`、`outputs/scenarios.json`、`ISSUES.md` 第一节 |
| 3 | [major] S05 的脱敏摘要是场景函数自己拼的字典，没有以 A 会所身份读取已转介商机 | 未改 | 新增接口桩 `api_read_opportunity_as_site(opp, site)`：按 `opportunity.site_id` 判定视角，本会所返回完整 jsonb（含 `amount_cent`/`ent_id`/`owner_id`），跨会所仅返回 `{id, stage, ent_name:'某企业（脱敏）'}`；`S05.sql` 同时以 A、B 身份各读一次并断言**字段集合** | `S05` 实际结果：`A 视角字段={ent_name,id,stage}`、`B 视角字段={amount_cent,ent_id,ent_name,id,owner_id,stage}` |
| 4 | [major] S03 联系人始终留在 site-a，没有真正跨会所 | 未改 | `api_change_contact_owner(contact, new_owner, new_site)` 真实改 `contact.site_id` + 写 `contact_owner_history`；`S03.sql` 断言 `contact.site=S2`、历史 1 条、变更后 S2 可见 1 行 / S1 可见 0 行（两个会所各调一次同一读取路径 `api_visible_contacts`） | `S03` 实际结果 |
| 5 | [minor] ISSUES.md 只有一句「0 条」，未写执行环境 | 未改 | `ISSUES.md` 改为「执行环境 + 12 场景结果表 + 问题单」三段：库版本（16.4）、15 张表清单、10 个接口桩清单、事务隔离方式、数据虚构声明；场景改为真实执行后按实际结果出单 | `ISSUES.md` 第一节 |

## 结构
| 文件 | 说明 |
|---|---|
| `sql/00_schema.sql` | PostgreSQL DDL：15 张表（site / enterprise / enterprise_site / event / opportunity / sop_task / contact / contact_owner_history / knowledge_article / dict_entry / site_config / group_config / event_registration / referral / scenario_result）+ 5 个索引 |
| `sql/01_seed.sql` | 虚构数据：3 个有效会所（S1/S2/S3）+ 1 个软删除会所（S9）、E01–E23、软删除企业 E90、已离场关系、S3 超容量、公开/私有活动、机构/会所字典与配置 |
| `sql/00_api_pg.sql` | **接口桩**（PL/pgSQL 10 个函数）：联系人换负责人（409 停业保护）、商机转介、活动报名（403 私有活动）、KB 读取（404 语义）、字典覆写保护、配置回落、可见联系人、按会所视角读商机 |
| `sql/scenarios/S01~S12.sql` | 12 个场景脚本，逐份真实 SQL / 接口调用，脚本末尾自写 `scenario_result` |
| `sql/1*_agg_*.sql` / `sql/2*_site_*.sql` | 5 条总部汇总 SQL（无 `GROUP BY`）/ 5 条按 `:site_id` 的单会所 SQL（含 `GROUP BY`） |
| `tools/run_sql.py` | 在 `DATABASE_URL` 指向的 PG 上执行 10 条 SQL 并对拍；无 DSN 时 SQLite 复跑并把结果写 `sql_results.sqlite.json` |
| `tools/run_matrix.py` | 建库 → 逐个执行 12 个场景脚本 → 生成 `scenarios.json` / `matrix-full.md` / `matrix-scenarios.md` |
| `app/dbtest.py` | 场景执行器：连接 / 建库 / 单场景事务执行 + ROLLBACK；不做任何业务计算 |
| `app/report.py` / `app/issues.py` | 矩阵渲染（场景｜期望行为｜执行脚本｜实际结果｜结论）/ 问题单生成（涉及表、接口、建议改法） |
| `probe.py` | 消费 `scenarios.json` + `sql_results.json` → 生成 `matrix-full.md`、`ISSUES.md`（含执行环境） |
| `verify.py` | 跑 pytest → 解析 junit → 分组矩阵 + `verify.json` + `run-report.md` |
| `tests/test_2442.py` | 场景/口径用例（三栏、脚本哈希、AC2/AC3、边界与隔离）；在线实跑、离线读 PG 产物两种模式 |
| `tests/test_2442_sql.py` | SQL 层 19 个用例：文件齐备、方言、汇总=各会所之和、非恒等式、软删除过滤、空置不为负、跨引擎一致 |
| `outputs/` | `sql_results.json`、`sql_results.sqlite.json`、`sql_report.md`、`scenarios.json`、`matrix-full.md`、`matrix-scenarios.md`、`verify.json`、`run-report.md`、`pytest-output.txt`、`junit.xml` |
| `ISSUES.md` | 执行环境 + 12 场景结果 + 问题单（本轮 0 条） |

## 对齐验收标准
| AC | 实现与用例 |
|---|---|
| 1 12 个场景各有期望行为、执行脚本、实际结果三栏 | `sql/scenarios/S01~S12.sql`（执行脚本可点开、可单跑）；`outputs/matrix-full.md` 12 行 5 栏；`test_01`（12 条参数化）、`test_02`、`test_03` |
| 2 5 个汇总查询结果等于各会所单独查询之和（pytest 断言通过） | `sql/10~14` 与 `sql/20~24` 在 **PostgreSQL 16.4** 执行；`test_sql_06`（5 项参数化、diff=0）、`test_sql_07`（非恒等式）、`test_sql_08`（SOP 15/20）；实测值：在驻企业 23、活动 11、签约 6、SOP 0.75、空置 21 |
| 3 所有不一致场景都有问题单（涉及表/接口/建议改法） | `test_08`（全一致 → 0 条）、`test_09`（注入不一致 → 出单字段齐全）、`test_10`（条数=不一致数）；`ISSUES.md` 第三节 |

## 12 个场景的实际结果
见 `outputs/matrix-full.md`（PG 16.4 执行后生成，含每份脚本的 sha256）。本批 12 个场景全部与期望一致，
`ISSUES.md` 为 0 条——这是真实结论，不是空跑：`test_09`/`test_10` 通过注入不一致验证「出单」通路有效。

## 口径说明
- **在驻企业数** = 企业-会所入驻关系数（在驻关系数口径：同一企业双会所计 2），排除软删除会所与软删除企业；
  `10_agg_member_count.sql` 注释中说明 `distinct_enterprises`（按企业唯一计数）仅供口径参考，不参与求和断言。
- **月度活动场次** 按 `event.month='2026-11'`，排除软删除会所。
- **商机转化数** = `stage='signed'`，排除软删除会所。
- **SOP 完成率** = Σdone / Σtotal（分子分母分别求和后相除）；对拍路径为「分会所完成率按样本量加权平均」。
- **空置工位数** = 工位容量 − 在驻关系数，超出容量记 0，不出现负数。
- **软删除**：`deleted_at IS NOT NULL` 的记录不出现在任何列表/导出，但物理行保留（S11 验证）。

## 环境说明（如实披露）
本交付包在 Windows + 便携版 PostgreSQL 16.4（`initdb` 本地实例，端口 55432）上实跑。
复跑时用你自己的 PG 16 实例即可，脚本内不含任何本机绝对路径；`sql/` 下 SQL 为标准 PostgreSQL 方言，
`sql/00_api_pg.sql` 需 PG 14+（PL/pgSQL + `jsonb`）。
