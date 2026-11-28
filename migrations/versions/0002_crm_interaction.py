"""创建互动记录表 crm_interaction：字段、CHECK、DESC 复合索引与 GIN 三元组索引。

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
    sa.Column("company_id", sa.Uuid(), nullable=False),
    sa.Column("contact_id", sa.Uuid()),
    sa.Column("type", sa.String(20), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("duration_minutes", sa.Integer()),
    sa.Column("summary", sa.Text(), nullable=False),
    sa.Column("next_action", sa.String(200)),
    sa.Column("next_action_due", sa.Date()),
    sa.Column("lead_id", sa.Uuid()),
    sa.Column("opportunity_id", sa.Uuid()),
    sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
    sa.Column("owner_user_id", sa.Uuid()),
    sa.Column("merged_into_id", sa.Uuid()),
]

CHECKS = [
    sa.CheckConstraint("type IN ('visit', 'call', 'wechat', 'meeting', 'event', 'email', 'other')", name="ck_int_type_enum"),
    sa.CheckConstraint("duration_minutes IS NULL OR duration_minutes BETWEEN 0 AND 1440", name="ck_int_duration_range"),
    sa.CheckConstraint("length(summary) BETWEEN 1 AND 5000", name="ck_int_summary_len"),
    sa.CheckConstraint("source IN ('manual', 'import', 'system')", name="ck_int_source_enum"),
]

IDX_DESC = [
    ("ix_int_org_company_occ", ["org_id", "company_id", sa.text("occurred_at DESC")]),
    ("ix_int_org_contact_occ", ["org_id", "contact_id", sa.text("occurred_at DESC")]),
    ("ix_int_org_owner_occ", ["org_id", "owner_user_id", sa.text("occurred_at DESC")]),
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table("crm_interaction", *COLS, *CHECKS)
    with op.batch_alter_table("crm_interaction") as batch:
        batch.create_foreign_key("fk_interaction_company_id", "crm_company", ["company_id"], ["id"])
        batch.create_foreign_key("fk_interaction_contact_id", "crm_contact", ["contact_id"], ["id"])
    for name, cols in IDX_DESC:
        op.create_index(name, "crm_interaction", cols)
    if bind.dialect.name == "postgresql":
        op.create_index("ix_int_summary_trgm", "crm_interaction", ["summary"],
                        postgresql_using="gin", postgresql_ops={"summary": "gin_trgm_ops"})
    else:
        # SQLite 无 gin_trgm_ops：降级为普通索引，语义一致由 README 说明
        op.create_index("ix_int_summary_trgm", "crm_interaction", ["summary"])
    # 自引用外键
    with op.batch_alter_table("crm_interaction") as batch:
        batch.create_foreign_key("fk_interaction_merged_into_id", "crm_interaction", ["merged_into_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("crm_interaction") as batch:
        batch.drop_constraint("fk_interaction_merged_into_id", type_="foreignkey")
        batch.drop_constraint("fk_interaction_contact_id", type_="foreignkey")
        batch.drop_constraint("fk_interaction_company_id", type_="foreignkey")
    op.drop_index("ix_int_summary_trgm", table_name="crm_interaction")
    for name, _cols in reversed(IDX_DESC):
        op.drop_index(name, table_name="crm_interaction")
    op.drop_table("crm_interaction")
