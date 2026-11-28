"""占位基座：crm_company 最小占位表（真实企业表迁移在其他工单）。

Revision ID: 0001
Revises: None
Create Date: 2026-11-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_company",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("credit_code", sa.String(32)),
    )


def downgrade() -> None:
    op.drop_table("crm_company")
