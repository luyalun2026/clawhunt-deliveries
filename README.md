# 工单 #2763 · S2-CRM-002 联系人表 crm_contact 模型与迁移

SQLAlchemy 2 模型 + Alembic 迁移 + 约束测试。测试数据全部虚构。

## 一、验收标准逐条对照（pytest 实跑）

| 验收标准 | 交付物 | 验证方式 |
|---|---|---|
| 1. upgrade/downgrade 往返成功，alembic check 零漂移 | migrations/versions/0001+0002 | tests/test_00_alembic_check.py 进程内 `alembic check`；test_ac1_roundtrip_and_zero_drift 断言往返后表结构完整 |
| 2. 同企业第二个 primary 被拒，第一个改 staff 后可插入 | uq_contact_company_primary 部分唯一索引 (company_id) WHERE member_identity='primary' AND deleted_at IS NULL | TestAC2PrimaryUnique 断言 IntegrityError → 改档 → 复插成功 |
| 3. bound 且 unionid 空被 CHECK 拒 | ck_contact_bound_unionid | TestAC3BoundUnionidCheck 双向断言 |
| 4. 同 org 未删除联系人 unionid 冲突被拒、异 org 共存 | uq_contact_org_unionid (org_id, wechat_unionid) WHERE deleted_at IS NULL AND wechat_unionid IS NOT NULL | TestAC4OrgUnionidPartialUnique 双例 + 软删除复用例 |

## 二、字段与约束表

| 字段 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| id | UUID | 否 | uuid4 | 主键（统一公共字段） |
| org_id / site_id / created_at / created_by / updated_at / deleted_at | — | — | — | 统一公共字段（软删除） |
| company_id | UUID FK→crm_company.id | 是 | — | 尚未关联企业的线索联系人为空 |
| name | varchar(50) | 否 | — | 姓名 |
| title | varchar(50) | 是 | — | 职务 |
| mobile | varchar(16) | 是 | — | E.164 规范存储；normalize_mobile() 归一化 |
| email | varchar(120) | 是 | — | |
| member_identity | varchar(20) | 否 | none | none / primary / staff（crm/enums.py） |
| wechat_unionid | varchar(64) | 是 | — | |
| wechat_openid | varchar(64) | 是 | — | |
| wechat_bind_status | varchar(20) | 否 | unbound | unbound / bound / revoked |
| wechat_bound_at | timestamptz | 是 | — | |
| merged_into_id | UUID FK→crm_contact.id | 是 | — | 自引用合并 |

**索引**
- 部分唯一 uq_contact_org_unionid (org_id, wechat_unionid) WHERE deleted_at IS NULL AND wechat_unionid IS NOT NULL
- 部分唯一 uq_contact_org_mobile (org_id, mobile) WHERE deleted_at IS NULL AND mobile IS NOT NULL
- 部分唯一 uq_contact_company_primary (company_id) WHERE member_identity='primary' AND deleted_at IS NULL
- 普通 ix_contact_org_company、ix_contact_org_identity

**CHECK**
- ck_contact_bound_unionid：bound ⟹ unionid 非空
- ck_contact_identity_company：member_identity ≠ none ⟹ company_id 非空
- 枚举白名单两处（与 crm/enums.py 同源）

## 三、占位与接线点

- 迁移 0001 为 **crm_company 占位 stub**（最小公共字段+name/credit_code）：企业表迁移属其他工单，
  本迁移 down_revision 链于其占位 revision。真实企业表合入后，将 0001 的 down_revision 改接真实
  链头并删除占位表即可，0002 无需改动。
- crm_contact.company_id 的 FK 直接指向 crm_company.id，无需改动。
- merged_into_id 自引用 FK 用 use_alter（迁移内表建好后补建）。

## 四、双环境说明

- 本包测试默认跑 **SQLite 等价承载**（部分唯一索引 WHERE / CHECK 语义与 PG16 一致），克隆即跑。
- PG16 专属 DDL 见 `pg_ddl.sql`（timestamptz 等）；设 `PG_DSN` 环境变量后 conftest 自动改用 PostgreSQL 跑同一套用例。

## 五、复现

```bash
git clone --branch 2763 https://github.com/luyalun2026/clawhunt-deliveries.git
cd clawhunt-deliveries
python -m pytest tests -q            # 见 outputs/run-report.md 的实测汇总
python verify.py                     # 重新生成 outputs/（junit.xml / verify.json / run-report.md）
```
