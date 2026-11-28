"""crm_lead 占位模型（stub）：真实线索表属其他工单；本包需要
converted_opportunity_id 列存在以便迁移 0002 补建外键。"""

import sqlalchemy as sa

from .base import Base, CommonMixin


class CrmLead(CommonMixin, Base):
    __tablename__ = "crm_lead"

    name = sa.Column(sa.String(120), nullable=False)
    converted_opportunity_id = sa.Column(sa.Uuid)
