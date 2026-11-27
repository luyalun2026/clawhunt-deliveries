"""init listening & daily stats tables (S6-POD-040)

Revision ID: 0001_pod040
Revises:
Create Date: 2026-11-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_pod040"
down_revision = None
branch_labels = None
depends_on = None

BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
JSON = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")
UUID = postgresql.UUID(as_uuid=False).with_variant(sa.String(36), "sqlite")


def upgrade() -> None:
    op.create_table(
        "episodes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("column_id", sa.String(64), index=True),
        sa.Column("title", sa.String(200)),
        sa.Column("duration_sec", sa.Integer, nullable=True),
    )
    op.create_table(
        "listening_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("org_id", sa.String(64), default="org_demo", index=True),
        sa.Column("site_id", sa.String(64), default="site_demo"),
        sa.Column("episode_id", sa.String(64),
                  sa.ForeignKey("episodes.id"), index=True),
        sa.Column("event_type", sa.String(32), index=True),
        sa.Column("session_id", sa.String(64), index=True, nullable=True),
        sa.Column("user_id", sa.String(64), index=True, nullable=True),
        sa.Column("anon_id", sa.String(64), index=True, nullable=True),
        sa.Column("source", sa.String(32), default="unknown"),
        sa.Column("played_delta_sec", sa.Integer, nullable=True),
        sa.Column("progress_pct", sa.Float, nullable=True),
        sa.Column("ts", sa.DateTime, index=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
    )
    op.create_table(
        "episode_daily_stats",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("org_id", sa.String(64), index=True),
        sa.Column("site_id", sa.String(64), default="site_demo"),
        sa.Column("episode_id", sa.String(64), index=True),
        sa.Column("column_id", sa.String(64), index=True, nullable=True),
        sa.Column("stat_date", sa.Date, index=True),
        sa.Column("views", BIGINT, default=0),
        sa.Column("plays", BIGINT, default=0),
        sa.Column("unique_listeners", BIGINT, default=0),
        sa.Column("listen_seconds", BIGINT, default=0),
        sa.Column("completes", BIGINT, default=0),
        sa.Column("completion_rate", sa.Float, nullable=True),
        sa.Column("avg_listen_ratio", sa.Float, nullable=True),
        *[sa.Column(f"reach_{lv}", BIGINT, default=0)
          for lv in range(10, 101, 10)],
        sa.Column("source_breakdown", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("org_id", "episode_id", "stat_date",
                            name="ux_episode_daily"),
    )
    op.create_table(
        "column_daily_stats",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("org_id", sa.String(64), index=True),
        sa.Column("site_id", sa.String(64), default="site_demo"),
        sa.Column("column_id", sa.String(64), index=True),
        sa.Column("stat_date", sa.Date, index=True),
        sa.Column("views", BIGINT, default=0),
        sa.Column("plays", BIGINT, default=0),
        sa.Column("unique_listeners", BIGINT, default=0),
        sa.Column("listen_seconds", BIGINT, default=0),
        sa.Column("completes", BIGINT, default=0),
        sa.Column("completion_rate", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("org_id", "column_id", "stat_date",
                            name="ux_column_daily"),
    )


def downgrade() -> None:
    op.drop_table("column_daily_stats")
    op.drop_table("episode_daily_stats")
    op.drop_table("listening_events")
    op.drop_table("episodes")
