import uuid

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """项目统一 DeclarativeBase（工单统一技术约定）。"""


class CommonMixin:
    """统一公共字段：id(UUID) / org_id / site_id / created_at / created_by / updated_at / deleted_at（软删除）。"""

    id = sa.Column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(sa.Uuid, nullable=False)
    site_id = sa.Column(sa.Uuid)
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    created_by = sa.Column(sa.Uuid)
    updated_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())
    deleted_at = sa.Column(sa.DateTime(timezone=True))
