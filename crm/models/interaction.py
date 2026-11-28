import sqlalchemy as sa

from .base import Base, CommonMixin
from ..enums import InteractionSource, InteractionType


class CrmInteraction(CommonMixin, Base):
    """互动记录表 crm_interaction（工单 #2770）。

    约束要点：
    - type 7 档枚举、source 3 档枚举（CHECK，与 crm/enums.py 同源）；
    - duration_minutes ∈ [0,1440]（可空）；summary 长度 ∈ [1,5000]；
    - 三个 DESC 复合索引服务「按企业/联系人/记录人取最近记录」；
    - summary 建 GIN 三元组索引（PG16 pg_trgm）供关键字搜索，SQLite 降级为普通索引；
    - lead_id / opportunity_id 本迁移只建列，外键由线索表、商机表迁移补建。
    """

    __tablename__ = "crm_interaction"

    company_id = sa.Column(sa.Uuid, sa.ForeignKey("crm_company.id", name="fk_interaction_company_id"), nullable=False)
    contact_id = sa.Column(sa.Uuid, sa.ForeignKey("crm_contact.id", name="fk_interaction_contact_id"))
    type = sa.Column("type", sa.String(20), nullable=False, key="type")
    occurred_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
    duration_minutes = sa.Column(sa.Integer)
    summary = sa.Column(sa.Text, nullable=False)
    next_action = sa.Column(sa.String(200))
    next_action_due = sa.Column(sa.Date)
    lead_id = sa.Column(sa.Uuid)
    opportunity_id = sa.Column(sa.Uuid)
    source = sa.Column(sa.String(20), nullable=False, default=InteractionSource.MANUAL.value)
    owner_user_id = sa.Column(sa.Uuid)
    merged_into_id = sa.Column(sa.Uuid, sa.ForeignKey("crm_interaction.id", name="fk_interaction_merged_into_id", use_alter=True))

    __table_args__ = (
        sa.CheckConstraint(f"type IN {InteractionType.sql_list()}", name="ck_int_type_enum"),
        sa.CheckConstraint("duration_minutes IS NULL OR duration_minutes BETWEEN 0 AND 1440", name="ck_int_duration_range"),
        sa.CheckConstraint("length(summary) BETWEEN 1 AND 5000", name="ck_int_summary_len"),
        sa.CheckConstraint(f"source IN {InteractionSource.sql_list()}", name="ck_int_source_enum"),
        sa.Index("ix_int_org_company_occ", "org_id", "company_id", sa.text("occurred_at DESC")),
        sa.Index("ix_int_org_contact_occ", "org_id", "contact_id", sa.text("occurred_at DESC")),
        sa.Index("ix_int_org_owner_occ", "org_id", "owner_user_id", sa.text("occurred_at DESC")),
        sa.Index("ix_int_summary_trgm", "summary", postgresql_using="gin", postgresql_ops={"summary": "gin_trgm_ops"}),
    )
