"""episode_conversion_stats 初始迁移

Revision ID: 0001_episode_stats
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_episode_stats"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "episode_conversion_stats",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("org_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("site_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("episode_id", sa.String(40), nullable=False),
        sa.Column("stat_date", sa.Date, nullable=False),
        sa.Column("intro_requests", sa.Integer, nullable=False, server_default="0"),
        sa.Column("intro_staff_approved", sa.Integer, nullable=False, server_default="0"),
        sa.Column("intro_accepted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("assisted_event_signups", sa.Integer, nullable=False, server_default="0"),
        sa.Column("assisted_course_signups", sa.Integer, nullable=False, server_default="0"),
        sa.Column("assisted_opportunity_requests", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("episode_id", "stat_date", name="uq_episode_stats"),
    )
    op.create_index("ix_episode_stats_date", "episode_conversion_stats",
                    ["stat_date", "episode_id"])


def downgrade() -> None:
    op.drop_index("ix_episode_stats_date", table_name="episode_conversion_stats")
    op.drop_table("episode_conversion_stats")
