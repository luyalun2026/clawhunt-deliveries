"""crm_interaction 占位模型（stub）：真实互动记录表属其他工单；
本包需要 opportunity_id 列存在以便迁移 0002 补建外键。"""

import sqlalchemy as sa

from .base import Base, CommonMixin


class CrmInteraction(CommonMixin, Base):
    __tablename__ = "crm_interaction"

    company_id = sa.Column(sa.Uuid)
    occurred_at = sa.Column(sa.DateTime(timezone=True))
    summary = sa.Column(sa.Text)
    opportunity_id = sa.Column(sa.Uuid)
