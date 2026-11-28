# 工单 #2771 · S2-CRM-006 招商商机表 crm_opportunity 模型与迁移

SQLAlchemy 2 模型 + Alembic 迁移（含两条补建外键）+ 约束测试。测试数据全部虚构。

## 一、验收标准逐条对照（pytest 实跑）

| 验收标准 | 交付物 | 验证方式 |
|---|---|---|
| 1. upgrade/downgrade 往返成功，alembic check 零漂移 | migrations/versions/0001+0002 | tests/test_00_alembic_check.py 进程内 `alembic check`；test_ac1_columns_and_roundtrip 断言列齐全 |
| 2. stage='lost' 且 lost_reason 为空被 CHECK 拒 | ck_opp_lost_reason_required | TestAC2LostReasonCheck 双向断言 |
| 3. expected_first_year_amount_fen 列 bigint 且负数被拒 | BigInteger 列 + ck_opp_amount_nonneg | TestAC3AmountColumnAndCheck：反射列类型 + 插入 -1 断言 IntegrityError |
| 4. 两条补建外键 upgrade 后存在、downgrade 后移除 | 0002 迁移 batch 补建 crm_interaction.opportunity_id 与 crm_lead.converted_opportunity_id | TestAC4BackfillForeignKeys PRAGMA/反射断言 + 迁移往返（downgrade 由 conftest teardown 完成后再 upgrade） |

## 二、字段表

| 字段 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| company_id | UUID FK→crm_company.id | 否 | — | 必填 |
| lead_id | UUID FK→crm_lead.id | 是 | — | 来源线索 |
| name | varchar(100) | 否 | — | 商机名称 |
| owner_user_id | UUID | 否 | — | 负责人 |
| stage | varchar(20) | 否 | discovery | 6 档枚举 |
| stage_changed_at | timestamptz | 是 | — | 应用层在 stage 变更时更新（不设触发器，README 注明） |
| expected_first_year_amount_fen | bigint | 是 | — | 预计首年金额（分），CHECK ≥0 |
| membership_tier | varchar(20) | 是 | — | flex / standard / premium / strategic |
| space_type | varchar(20) | 是 | — | hot_desk / fixed_desk / private_office / suite |
| seats_needed | int | 是 | — | CHECK ≥0 |
| area_sqm | numeric(8,2) | 是 | — | CHECK ≥0 |
| expected_move_in_date / expected_close_date | date | 是 | — | |
| win_probability | smallint | 是 | — | CHECK 0–100 |
| lost_reason | varchar(20) | 是 | — | 6 档枚举；lost 时必填 |
| closed_at | timestamptz | 是 | — | |
| merged_into_id | UUID FK→crm_opportunity.id | 是 | — | 自引用合并 |

**索引**：ix_opp_org_stage_close、ix_opp_org_owner_stage、ix_opp_org_company。

## 三、补建外键说明（本迁移同时负责）

- `crm_interaction.opportunity_id` → crm_opportunity.id（fk_interaction_opportunity_id）
- `crm_lead.converted_opportunity_id` → crm_opportunity.id（fk_lead_converted_opportunity_id）
- upgrade 补建、downgrade 移除，两侧对称（AC4 实测）。

## 四、占位与接线点

- 0001 为占位 stub：crm_company（最小公共字段）、crm_lead（含 converted_opportunity_id 列）、
  crm_interaction（含 opportunity_id 列）。真实表迁移合入后：改 0001 的 down_revision 链接到真实链头、
  删除占位建表段；0002 的 batch 补建外键段落保留不动即可。

## 五、双环境与复现

- 测试默认 SQLite 等价承载（CHECK/唯一约束/PRAGMA 外键校验语义一致），克隆即跑；PG16 环境设 `PG_DSN`
  后自动切 PostgreSQL；PG16 专属 DDL 见 `pg_ddl.sql`。

```bash
git clone --branch 2771 https://github.com/luyalun2026/clawhunt-deliveries.git
cd clawhunt-deliveries
python -m pytest tests -q            # 见 outputs/run-report.md 的实测汇总
python verify.py                     # 重新生成 outputs/
```
