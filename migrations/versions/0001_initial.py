# -*- coding: utf-8 -*-
"""0001 初始迁移：ip_project 与 ip_jobs（可逆：downgrade 删除两表）。"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ip_project",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("failed_step", sa.String(64), nullable=True),
        sa.Column("failed_segments", sa.String(512), nullable=True),
    )
    op.create_table(
        "ip_jobs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("step", sa.String(64), nullable=False),
        sa.Column("sub_step", sa.String(64), nullable=False, server_default=""),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.String(32), nullable=True),
        sa.Column("finished_at", sa.String(32), nullable=True),
        sa.Column("error_code", sa.String(128), nullable=True),
        sa.Column("org_id", sa.String(64), nullable=True),
        sa.Column("site_id", sa.String(64), nullable=True),
        sa.UniqueConstraint("project_id", "step", "sub_step", name="uq_ip_job_step"),
    )
    op.create_index("ix_ip_jobs_project_id", "ip_jobs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_ip_jobs_project_id", table_name="ip_jobs")
    op.drop_table("ip_jobs")
    op.drop_table("ip_project")
