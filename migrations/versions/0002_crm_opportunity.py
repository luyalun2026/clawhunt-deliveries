"""创建招商商机表 crm_opportunity 并补建两条外键。

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

CHECKS = [
    sa.CheckConstraint("stage IN ('discovery', 'site_visit', 'proposal', 'negotiation', 'won', 'lost')", name="ck_opp_stage_enum"),
    sa.CheckConstraint("stage <> 'lost' OR lost_reason IS NOT NULL", name="ck_opp_lost_reason_required"),
    sa.CheckConstraint("lost_reason IS NULL OR lost_reason IN ('price', 'location', 'space', 'competitor', 'timing', 'other')", name="ck_opp_lost_reason_enum"),
    sa.CheckConstraint("expected_first_year_amount_fen >= 0", name="ck_opp_amount_nonneg"),
    sa.CheckConstraint("win_probability IS NULL OR win_probability BETWEEN 0 AND 100", name="ck_opp_win_prob"),
    sa.CheckConstraint("membership_tier IS NULL OR membership_tier IN ('flex', 'standard', 'premium', 'strategic')", name="ck_opp_tier_enum"),
    sa.CheckConstraint("space_type IS NULL OR space_type IN ('hot_desk', 'fixed_desk', 'private_office', 'suite')", name="ck_opp_space_type_enum"),
    sa.CheckConstraint("seats_needed IS NULL OR seats_needed >= 0", name="ck_opp_seats_nonneg"),
    sa.CheckConstraint("area_sqm IS NULL OR area_sqm >= 0", name="ck_opp_area_nonneg"),
]

COLS = [
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("org_id", sa.Uuid(), nullable=False),
    sa.Column("site_id", sa.Uuid()),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("created_by", sa.Uuid()),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("deleted_at", sa.DateTime(timezone=True)),
    sa.Column("company_id", sa.Uuid(), nullable=False),
    sa.Column("lead_id", sa.Uuid()),
    sa.Column("name", sa.String(100), nullable=False),
    sa.Column("owner_user_id", sa.Uuid(), nullable=False),
    sa.Column("stage", sa.String(20), nullable=False, server_default="discovery"),
    sa.Column("stage_changed_at", sa.DateTime(timezone=True)),
    sa.Column("expected_first_year_amount_fen", sa.BigInteger()),
    sa.Column("membership_tier", sa.String(20)),
    sa.Column("space_type", sa.String(20)),
    sa.Column("seats_needed", sa.Integer()),
    sa.Column("area_sqm", sa.Numeric(8, 2)),
    sa.Column("expected_move_in_date", sa.Date()),
    sa.Column("expected_close_date", sa.Date()),
    sa.Column("win_probability", sa.SmallInteger()),
    sa.Column("lost_reason", sa.String(20)),
    sa.Column("closed_at", sa.DateTime(timezone=True)),
    sa.Column("merged_into_id", sa.Uuid()),
]

IDX = [
    ("ix_opp_org_stage_close", ["org_id", "stage", "expected_close_date"]),
    ("ix_opp_org_owner_stage", ["org_id", "owner_user_id", "stage"]),
    ("ix_opp_org_company", ["org_id", "company_id"]),
]


def upgrade() -> None:
    op.create_table("crm_opportunity", *COLS, *CHECKS)
    for name, cols in IDX:
        op.create_index(name, "crm_opportunity", cols)
    # 外键在表建立后补建（SQLite 走 batch 复制模式，PG 走原生 ALTER）
    with op.batch_alter_table("crm_interaction") as batch:
        batch.create_foreign_key("fk_interaction_opportunity_id", "crm_opportunity", ["opportunity_id"], ["id"])
    with op.batch_alter_table("crm_lead") as batch:
        batch.create_foreign_key("fk_lead_converted_opportunity_id", "crm_opportunity", ["converted_opportunity_id"], ["id"])
    # 自引用外键
    with op.batch_alter_table("crm_opportunity") as batch:
        batch.create_foreign_key("fk_opp_merged_into_id", "crm_opportunity", ["merged_into_id"], ["id"])
    # 业务外键（company_id 必填、lead_id 可空）
    with op.batch_alter_table("crm_opportunity") as batch:
        batch.create_foreign_key("fk_opp_company_id", "crm_company", ["company_id"], ["id"])
        batch.create_foreign_key("fk_opp_lead_id", "crm_lead", ["lead_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("crm_opportunity") as batch:
        batch.drop_constraint("fk_opp_lead_id", type_="foreignkey")
        batch.drop_constraint("fk_opp_company_id", type_="foreignkey")
        batch.drop_constraint("fk_opp_merged_into_id", type_="foreignkey")
    with op.batch_alter_table("crm_lead") as batch:
        batch.drop_constraint("fk_lead_converted_opportunity_id", type_="foreignkey")
    with op.batch_alter_table("crm_interaction") as batch:
        batch.drop_constraint("fk_interaction_opportunity_id", type_="foreignkey")
    for name, _cols in reversed(IDX):
        op.drop_index(name, table_name="crm_opportunity")
    op.drop_table("crm_opportunity")
