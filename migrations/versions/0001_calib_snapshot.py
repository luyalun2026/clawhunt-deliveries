"""calib schema 与 health_snapshot 初始迁移

Revision ID: 0001_calib_snapshot
Revises:
Create Date: 2026-12-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_calib_snapshot"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "calib"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    op.create_table(
        "health_snapshot",
        sa.Column("snapshot_date", sa.Date, primary_key=True),
        sa.Column("company_pid", sa.String(40), primary_key=True),
        sa.Column("site_code", sa.String(20), nullable=False),
        sa.Column("industry_code", sa.String(8), nullable=False),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.Column("membership_level", sa.String(20), nullable=False),
        sa.Column("tenure_days", sa.Integer, nullable=False),
        sa.Column("days_to_expiry", sa.Integer, nullable=False),
        sa.Column("event_raw", sa.Integer),
        sa.Column("interaction_raw", sa.Integer),
        sa.Column("resource_raw", sa.Integer),
        sa.Column("opportunity_raw", sa.Integer),
        sa.Column("space_raw", sa.Numeric(10, 2)),
        sa.Column("event_score", sa.Numeric(5, 2)),
        sa.Column("interaction_score", sa.Numeric(5, 2)),
        sa.Column("resource_score", sa.Numeric(5, 2)),
        sa.Column("opportunity_score", sa.Numeric(5, 2)),
        sa.Column("space_score", sa.Numeric(5, 2)),
        sa.Column("health_score", sa.Numeric(5, 2)),
        sa.Column("health_level", sa.String(20)),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("algorithm_version", sa.String(20), nullable=False, server_default="v1"),
        sa.UniqueConstraint("snapshot_date", "company_pid", name="uq_health_snapshot"),
        sa.CheckConstraint("tenure_days >= 0", name="ck_tenure_nonneg"),
        sa.CheckConstraint("health_score IS NULL OR (health_score BETWEEN 0 AND 100)",
                           name="ck_health_score_range"),
        sa.CheckConstraint("health_level IS NULL OR health_level IN ('A','B','C','D')",
                           name="ck_health_level"),
        sa.CheckConstraint("event_score IS NULL OR (event_score BETWEEN 0 AND 100)",
                           name="ck_event_score_range"),
        sa.CheckConstraint("interaction_score IS NULL OR (interaction_score BETWEEN 0 AND 100)",
                           name="ck_interaction_score_range"),
        sa.CheckConstraint("resource_score IS NULL OR (resource_score BETWEEN 0 AND 100)",
                           name="ck_resource_score_range"),
        sa.CheckConstraint("opportunity_score IS NULL OR (opportunity_score BETWEEN 0 AND 100)",
                           name="ck_opportunity_score_range"),
        sa.CheckConstraint("space_score IS NULL OR (space_score BETWEEN 0 AND 100)",
                           name="ck_space_score_range"),
        schema=SCHEMA,
    )
    op.create_index("ix_health_snapshot_date", "health_snapshot", ["snapshot_date"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_health_snapshot_date", table_name="health_snapshot", schema=SCHEMA)
    op.drop_table("health_snapshot", schema=SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA}")
