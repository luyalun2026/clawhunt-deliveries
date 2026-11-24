"""科目映射 / 导出审计 / 期间锁定 / 导出快照 初始迁移

Revision ID: 0001_accounting_export
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_accounting_export"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounting_mappings",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("fee_type", sa.String(40), nullable=False),
        sa.Column("revenue_account", sa.String(20), nullable=False),
        sa.Column("receivable_account", sa.String(20), nullable=False),
        sa.Column("tax_account", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.UniqueConstraint("fee_type", name="uq_fee_type"),
    )
    op.create_table(
        "export_runs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("export_type", sa.String(20), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("row_count", sa.Integer, server_default="0"),
        sa.Column("total_cents", sa.BigInteger, server_default="0"),
        sa.Column("file_sha256", sa.String(64), server_default=""),
        sa.Column("operator", sa.String(40), server_default="system"),
        sa.Column("is_adjustment", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_export_runs_period", "export_runs", ["period"])
    op.create_table(
        "period_locks",
        sa.Column("period", sa.String(7), primary_key=True),
        sa.Column("first_exported_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "export_snapshots",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("export_type", sa.String(20), nullable=False),
        sa.Column("row_key", sa.String(120), nullable=False),
        sa.Column("amount_cents", sa.BigInteger, nullable=False),
        sa.Column("snapshot_hash", sa.String(64), server_default=""),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("period", "export_type", "row_key", name="uq_snapshot_row"),
    )
    op.bulk_insert(
        sa.table("accounting_mappings",
                 sa.column("id", sa.Uuid(as_uuid=True)),
                 sa.column("fee_type", sa.String),
                 sa.column("revenue_account", sa.String),
                 sa.column("receivable_account", sa.String),
                 sa.column("tax_account", sa.String),
                 sa.column("is_active", sa.Boolean)),
        [
            {"id": "00000000-0000-0000-0000-000000000001", "fee_type": "场地费",
             "revenue_account": "6001.01", "receivable_account": "1122.01",
             "tax_account": "2221.01", "is_active": True},
            {"id": "00000000-0000-0000-0000-000000000002", "fee_type": "服务费",
             "revenue_account": "6001.02", "receivable_account": "1122.02",
             "tax_account": "2221.02", "is_active": True},
        ],
    )


def downgrade() -> None:
    op.drop_table("export_snapshots")
    op.drop_table("period_locks")
    op.drop_index("ix_export_runs_period", table_name="export_runs")
    op.drop_table("export_runs")
    op.drop_table("accounting_mappings")
