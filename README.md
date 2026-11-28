# 工单 #2770 · S2-CRM-004 互动记录表 crm_interaction 模型与迁移

SQLAlchemy 2 模型 + Alembic 迁移 + 约束测试 + 万条 EXPLAIN 复现脚本。测试数据全部虚构。

## 一、验收标准逐条对照（pytest 实跑）

| 验收标准 | 交付物 | 验证方式 |
|---|---|---|
| 1. upgrade/downgrade 往返成功，alembic check 零漂移 | migrations/versions/0001+0002 | tests/test_00_alembic_check.py 进程内 `alembic check`；test_ac1_columns_and_roundtrip 断言列齐全且 lead_id/opportunity_id 只建列不建外键 |
| 2. duration_minutes=1441、summary 空串或超 5000 字被 CHECK 拒 | ck_int_duration_range / ck_int_summary_len | TestAC2DurationAndSummaryChecks 三组反例 + 边界值（1440、1 字、5000 字）通过 |
| 3. 1 万条虚构互动按 company_id 取最近 20 条 EXPLAIN 命中 (org_id, company_id, occurred_at) 索引 | seed_10k.py + explain_query.py + ix_int_org_company_occ | TestAC3ExplainUsesCompositeIndex：PG_DSN 下 seed→EXPLAIN(ANALYZE)→断言计划含索引名并落盘 outputs/explain-output.txt；无 PG16 环境显式 skip 并提供一键复现命令 |

## 二、字段表

| 字段 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| company_id | UUID FK→crm_company.id | 否 | — | 必填 |
| contact_id | UUID FK→crm_contact.id | 是 | — | |
| type | varchar(20) | 否 | — | visit / call / wechat / meeting / event / email / other |
| occurred_at | timestamptz | 否 | — | 发生时间 |
| duration_minutes | int | 是 | — | CHECK 0–1440 |
| summary | text | 否 | — | CHECK length 1–5000 |
| next_action | varchar(200) | 是 | — | |
| next_action_due | date | 是 | — | |
| lead_id / opportunity_id | UUID | 是 | — | 本迁移只建列，外键由线索表、商机表迁移补建 |
| source | varchar(20) | 否 | manual | manual / import / system |
| owner_user_id | UUID | 是 | — | 记录人 |
| merged_into_id | UUID FK→crm_interaction.id | 是 | — | 自引用合并 |

**索引**
- DESC 复合索引三处：ix_int_org_company_occ / ix_int_org_contact_occ / ix_int_org_owner_occ，
  均为 (org_id, <维度>, occurred_at DESC)，服务"按企业/联系人/记录人取最近记录"
- ix_int_summary_trgm：PG16 上为 GIN 三元组索引（pg_trgm，summary 关键字模糊搜索）；
  SQLite 无 gin_trgm_ops，降级为普通索引（语义差异在 README 与迁移内注明）

## 三、AC3 复现（需真实 PG16）

```bash
export PG_DSN=postgresql://user:pass@host:5432/db
python seed_10k.py        # 灌入 1 万条虚构互动
python explain_query.py   # 输出 EXPLAIN(ANALYZE) 全文并断言命中 ix_int_org_company_occ
```
EXPLAIN 全文由脚本自动写入 outputs/explain-output.txt 并打印（不手写数字）。
本包开发环境无 PG16/docker，该断言在无 PG_DSN 时显式 skip（skipif 落盘留痕），
pg_ddl.sql 提供 DBA 一键审阅的 PG16 专属 DDL（timestamptz / pg_trgm / GIN）。

## 四、占位与接线点

- 0001 为占位 stub：crm_company、crm_contact（最小公共字段）。真实表迁移合入后改 down_revision
  链接并删除占位段；crm_interaction 的 company_id/contact_id 外键无需改动。
- lead_id / opportunity_id 外键预留：线索表（#2772）与商机表（#2771）迁移补建。

## 五、复现

```bash
git clone --branch 2770 https://github.com/luyalun2026/clawhunt-deliveries.git
cd clawhunt-deliveries
python -m pytest tests -q            # 见 outputs/run-report.md 的实测汇总
python verify.py                     # 重新生成 outputs/
```
