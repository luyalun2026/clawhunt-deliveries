"""银行流水导入三张表初始迁移

Revision ID: 0001_bank_import
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_bank_import"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_statement_templates",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("bank_code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("encoding", sa.String(20), server_default="utf-8-sig"),
        sa.Column("columns", sa.JSON, nullable=False),
        sa.Column("amount_sign_rule", sa.String(20), server_default="direction"),
        sa.Column("date_formats", sa.JSON),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        "bank_import_batches",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("template_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("bank_statement_templates.id"), nullable=True),
        sa.Column("filename", sa.String(200), server_default=""),
        sa.Column("file_sha256", sa.String(64), server_default=""),
        sa.Column("account_no", sa.String(40), nullable=False),
        sa.Column("total_rows", sa.Integer, server_default="0"),
        sa.Column("added", sa.Integer, server_default="0"),
        sa.Column("skipped_dup", sa.Integer, server_default="0"),
        sa.Column("skipped_debit", sa.Integer, server_default="0"),
        sa.Column("failed", sa.Integer, server_default="0"),
        sa.Column("errors", sa.JSON),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("elapsed_ms", sa.Integer, server_default="0"),
    )
    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("batch_id", sa.Uuid(as_uuid=True), sa.ForeignKey("bank_import_batches.id")),
        sa.Column("account_no", sa.String(40), nullable=False),
        sa.Column("bank_serial", sa.String(64), nullable=False),
        sa.Column("txn_date", sa.Date, nullable=False),
        sa.Column("amount_cents", sa.BigInteger, nullable=False),
        sa.Column("counterparty_name", sa.String(120), server_default=""),
        sa.Column("counterparty_account", sa.String(64), server_default=""),
        sa.Column("memo", sa.String(240), server_default=""),
        sa.Column("status", sa.String(20), server_default="unmatched"),
        sa.UniqueConstraint("account_no", "bank_serial", name="uq_bank_txn"),
        sa.CheckConstraint("status IN ('unmatched','suggested','matched','ignored')",
                           name="ck_txn_status"),
    )


def downgrade() -> None:
    op.drop_table("bank_transactions")
    op.drop_table("bank_import_batches")
    op.drop_table("bank_statement_templates")
