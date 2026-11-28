"""crm_company 占位模型（stub）。

工单 #%(tid)s 依赖企业表，但企业表迁移属于其他工单。此处按统一技术约定定义
**最小占位结构**（仅公共字段 + name），真实企业表迁移合入后由该工单替换，
README 的「占位与接线点」一节写明对接点。
"""

import sqlalchemy as sa

from .base import Base, CommonMixin


class CrmCompany(CommonMixin, Base):
    __tablename__ = "crm_company"

    name = sa.Column(sa.String(120), nullable=False)
    credit_code = sa.Column(sa.String(32))
