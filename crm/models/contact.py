"""crm_contact 占位模型（stub）：真实联系人表属工单 #2763；
本包需要 contact_id 外键指向它，README 写明接线点。"""

import sqlalchemy as sa

from .base import Base, CommonMixin


class CrmContact(CommonMixin, Base):
    __tablename__ = "crm_contact"

    name = sa.Column(sa.String(50), nullable=False)
