"""初始迁移：page_daily_stats / funnel_daily_stats / monthly_active_companies

Revision ID: 0001_daily_stats
Revises:
Create Date: 2026-12-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_daily_stats"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "page_daily_stats",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("org_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("site_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("stat_date", sa.Date, nullable=False),
        sa.Column("page", sa.String(200), nullable=False),
        sa.Column("pv", sa.Integer, nullable=False, server_default="0"),
        sa.Column("uv", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(64)),
        sa.Column("deleted_at", sa.DateTime),
        sa.UniqueConstraint("stat_date", "site_id", "page", name="uq_page_daily"),
        sa.CheckConstraint("pv >= 0 AND uv >= 0", name="ck_page_daily_nonneg"),
    )
    op.create_index("ix_page_daily_site_date", "page_daily_stats", ["site_id", "stat_date"])

    op.create_table(
        "funnel_daily_stats",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("org_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("site_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("stat_date", sa.Date, nullable=False),
        sa.Column("funnel_code", sa.String(40), nullable=False),
        sa.Column("scope_key", sa.String(64), nullable=False, server_default="-"),
        sa.Column("step_key", sa.String(40), nullable=False),
        sa.Column("step_index", sa.Integer, nullable=False),
        sa.Column("user_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("stat_date", "site_id", "funnel_code", "scope_key", "step_key",
                            name="uq_funnel_daily"),
        sa.CheckConstraint("step_index >= 1", name="ck_funnel_step_index"),
        sa.CheckConstraint("user_count >= 0", name="ck_funnel_nonneg"),
    )
    op.create_index("ix_funnel_site_date", "funnel_daily_stats", ["site_id", "stat_date"])

    op.create_table(
        "monthly_active_companies",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("org_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("site_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("company_pid", sa.String(40), nullable=False),
        sa.UniqueConstraint("month", "site_id", "company_pid", name="uq_mac"),
    )
    op.create_index("ix_mac_month", "monthly_active_companies", ["month"])


def downgrade() -> None:
    op.drop_index("ix_mac_month", table_name="monthly_active_companies")
    op.drop_table("monthly_active_companies")
    op.drop_index("ix_funnel_site_date", table_name="funnel_daily_stats")
    op.drop_table("funnel_daily_stats")
    op.drop_index("ix_page_daily_site_date", table_name="page_daily_stats")
    op.drop_table("page_daily_stats")
