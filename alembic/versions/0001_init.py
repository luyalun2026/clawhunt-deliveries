"""init ai_drafts + ai_draft_events

Revision ID: 0001
Revises:
Create Date: 2026-11-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=True),
        sa.Column("site_id", sa.String(64), nullable=True),
        sa.Column("feature_code", sa.String(64), index=True),
        sa.Column("source_type", sa.String(64)),
        sa.Column("source_id", sa.String(128)),
        sa.Column("title", sa.String(256)),
        sa.Column("ai_content", sa.JSON),
        sa.Column("schema_id", sa.String(64)),
        sa.Column("schema_version", sa.String(32)),
        sa.Column("gw_request_id", sa.String(128), unique=True, index=True),
        sa.Column("drafter_id", sa.String(64)),
        sa.Column("requested_level", sa.String(16)),
        sa.Column("final_level", sa.String(16)),
        sa.Column("status", sa.String(16), index=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(64)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "ai_draft_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(32), index=True),
        sa.Column("draft_id", sa.String(36), index=True),
        sa.Column("feature_code", sa.String(64)),
        sa.Column("source_type", sa.String(64)),
        sa.Column("source_id", sa.String(128)),
        sa.Column("payload", sa.JSON),
        sa.Column("delivery_attempts", sa.Integer),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("ai_draft_events")
    op.drop_table("ai_drafts")
