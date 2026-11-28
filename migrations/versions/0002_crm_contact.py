"""创建联系人表 crm_contact：字段、三处部分唯一索引、CHECK、普通索引。

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

COLS = [
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("org_id", sa.Uuid(), nullable=False),
    sa.Column("site_id", sa.Uuid()),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("created_by", sa.Uuid()),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("deleted_at", sa.DateTime(timezone=True)),
    sa.Column("company_id", sa.Uuid(), sa.ForeignKey("crm_company.id", name="fk_contact_company_id")),
    sa.Column("name", sa.String(50), nullable=False),
    sa.Column("title", sa.String(50)),
    sa.Column("mobile", sa.String(16)),
    sa.Column("email", sa.String(120)),
    sa.Column("member_identity", sa.String(20), nullable=False, server_default="none"),
    sa.Column("wechat_unionid", sa.String(64)),
    sa.Column("wechat_openid", sa.String(64)),
    sa.Column("wechat_bind_status", sa.String(20), nullable=False, server_default="unbound"),
    sa.Column("wechat_bound_at", sa.DateTime(timezone=True)),
    sa.Column("merged_into_id", sa.Uuid()),
]

CHECKS = [
    sa.CheckConstraint("wechat_bind_status <> 'bound' OR wechat_unionid IS NOT NULL", name="ck_contact_bound_unionid"),
    sa.CheckConstraint("member_identity = 'none' OR company_id IS NOT NULL", name="ck_contact_identity_company"),
    sa.CheckConstraint("member_identity IN ('none', 'primary', 'staff')", name="ck_contact_identity_enum"),
    sa.CheckConstraint("wechat_bind_status IN ('unbound', 'bound', 'revoked')", name="ck_contact_bind_enum"),
]

UP_WHERE_UNIONID = sa.text("deleted_at IS NULL AND wechat_unionid IS NOT NULL")
UP_WHERE_MOBILE = sa.text("deleted_at IS NULL AND mobile IS NOT NULL")
UP_WHERE_PRIMARY = sa.text("member_identity = 'primary' AND deleted_at IS NULL")


def upgrade() -> None:
    op.create_table("crm_contact", *COLS, *CHECKS)
    op.create_index("uq_contact_org_unionid", "crm_contact", ["org_id", "wechat_unionid"], unique=True,
                    sqlite_where=UP_WHERE_UNIONID, postgresql_where=UP_WHERE_UNIONID)
    op.create_index("uq_contact_org_mobile", "crm_contact", ["org_id", "mobile"], unique=True,
                    sqlite_where=UP_WHERE_MOBILE, postgresql_where=UP_WHERE_MOBILE)
    op.create_index("uq_contact_company_primary", "crm_contact", ["company_id"], unique=True,
                    sqlite_where=UP_WHERE_PRIMARY, postgresql_where=UP_WHERE_PRIMARY)
    op.create_index("ix_contact_org_company", "crm_contact", ["org_id", "company_id"])
    op.create_index("ix_contact_org_identity", "crm_contact", ["org_id", "member_identity"])
    # 自引用外键（use_alter）：表建好后补（SQLite 走 batch 复制模式）
    with op.batch_alter_table("crm_contact") as batch:
        batch.create_foreign_key("fk_contact_merged_into_id", "crm_contact", ["merged_into_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("crm_contact") as batch:
        batch.drop_constraint("fk_contact_merged_into_id", type_="foreignkey")
    op.drop_index("ix_contact_org_identity", table_name="crm_contact")
    op.drop_index("ix_contact_org_company", table_name="crm_contact")
    op.drop_index("uq_contact_company_primary", table_name="crm_contact")
    op.drop_index("uq_contact_org_mobile", table_name="crm_contact")
    op.drop_index("uq_contact_org_unionid", table_name="crm_contact")
    op.drop_table("crm_contact")
