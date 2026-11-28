import sqlalchemy as sa

from .base import Base, CommonMixin
from ..enums import LostReason, MembershipTier, OpportunityStage, SpaceType


class CrmOpportunity(CommonMixin, Base):
    """招商商机表 crm_opportunity（工单 #2771）。

    约束要点：
    - stage='lost' 时 lost_reason 必填（CHECK）；
    - 金额以分存整数，bigint 列且 >= 0；
    - win_probability ∈ [0,100]；
    - 迁移同时补建 crm_interaction.opportunity_id 与 crm_lead.converted_opportunity_id 两条外键
      （见 migrations/versions/0002，downgrade 对称移除）。
    """

    __tablename__ = "crm_opportunity"

    company_id = sa.Column(sa.Uuid, sa.ForeignKey("crm_company.id", name="fk_opp_company_id"), nullable=False)
    lead_id = sa.Column(sa.Uuid, sa.ForeignKey("crm_lead.id", name="fk_opp_lead_id"))
    name = sa.Column(sa.String(100), nullable=False)
    owner_user_id = sa.Column(sa.Uuid, nullable=False)
    stage = sa.Column(sa.String(20), nullable=False, default=OpportunityStage.DISCOVERY.value)
    stage_changed_at = sa.Column(sa.DateTime(timezone=True))
    expected_first_year_amount_fen = sa.Column(sa.BigInteger, nullable=True)
    membership_tier = sa.Column(sa.String(20))
    space_type = sa.Column(sa.String(20))
    seats_needed = sa.Column(sa.Integer)
    area_sqm = sa.Column(sa.Numeric(8, 2))
    expected_move_in_date = sa.Column(sa.Date)
    expected_close_date = sa.Column(sa.Date)
    win_probability = sa.Column(sa.SmallInteger)
    lost_reason = sa.Column(sa.String(20))
    closed_at = sa.Column(sa.DateTime(timezone=True))
    merged_into_id = sa.Column(sa.Uuid, sa.ForeignKey("crm_opportunity.id", name="fk_opp_merged_into_id", use_alter=True))

    __table_args__ = (
        sa.CheckConstraint(f"stage IN {OpportunityStage.sql_list()}", name="ck_opp_stage_enum"),
        sa.CheckConstraint(
            "stage <> 'lost' OR lost_reason IS NOT NULL",
            name="ck_opp_lost_reason_required",
        ),
        sa.CheckConstraint(f"lost_reason IS NULL OR lost_reason IN {LostReason.sql_list()}", name="ck_opp_lost_reason_enum"),
        sa.CheckConstraint("expected_first_year_amount_fen >= 0", name="ck_opp_amount_nonneg"),
        sa.CheckConstraint("win_probability IS NULL OR win_probability BETWEEN 0 AND 100", name="ck_opp_win_prob"),
        sa.CheckConstraint(f"membership_tier IS NULL OR membership_tier IN {MembershipTier.sql_list()}", name="ck_opp_tier_enum"),
        sa.CheckConstraint(f"space_type IS NULL OR space_type IN {SpaceType.sql_list()}", name="ck_opp_space_type_enum"),
        sa.CheckConstraint("seats_needed IS NULL OR seats_needed >= 0", name="ck_opp_seats_nonneg"),
        sa.CheckConstraint("area_sqm IS NULL OR area_sqm >= 0", name="ck_opp_area_nonneg"),
        sa.Index("ix_opp_org_stage_close", "org_id", "stage", "expected_close_date"),
        sa.Index("ix_opp_org_owner_stage", "org_id", "owner_user_id", "stage"),
        sa.Index("ix_opp_org_company", "org_id", "company_id"),
    )
