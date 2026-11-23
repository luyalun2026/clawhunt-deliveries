# -*- coding: utf-8 -*-
"""0001 初始迁移（v3）：ip_project 与 ip_jobs，统一技术约定列齐全，可逆。

对应第 2 轮返工第 4 条：
* 两表主键均为 UUID（sa.Uuid：PG 原生 uuid / SQLite CHAR(32)）；
* 两表均含 org_id、site_id、created_at、created_by、updated_at、deleted_at；
* 时间列全部 DateTime(timezone=True)，不再使用字符串时间。
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ip_project",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=True),
        sa.Column("site_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("failed_step", sa.String(64), nullable=True),
        sa.Column("failed_segments", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ip_project_org_id", "ip_project", ["org_id"])
    op.create_index("ix_ip_project_site_id", "ip_project", ["site_id"])

    op.create_table(
        "ip_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("step", sa.String(64), nullable=False),
        sa.Column("sub_step", sa.String(64), nullable=False, server_default=""),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(128), nullable=True),
        sa.Column("org_id", sa.String(64), nullable=True),
        sa.Column("site_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id", "step", "sub_step", name="uq_ip_job_step"),
    )
    op.create_index("ix_ip_jobs_project_id", "ip_jobs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_ip_jobs_project_id", table_name="ip_jobs")
    op.drop_table("ip_jobs")
    op.drop_index("ix_ip_project_site_id", table_name="ip_project")
    op.drop_index("ix_ip_project_org_id", table_name="ip_project")
    op.drop_table("ip_project")
