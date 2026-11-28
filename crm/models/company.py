"""crm_company 占位模型（stub，真实企业表迁移在其他工单，README 写明接线点）。"""

import sqlalchemy as sa

from .base import Base, CommonMixin


class CrmCompany(CommonMixin, Base):
    __tablename__ = "crm_company"

    name = sa.Column(sa.String(120), nullable=False)
