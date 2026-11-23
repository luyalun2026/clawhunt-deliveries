# -*- coding: utf-8 -*-
"""#2288 v3 · SQLAlchemy 2 模型（统一技术约定，按返工意见整改）。

整改点（对应第 2 轮返工第 4 条）：
* ip_project / ip_jobs 主键均为 UUID（SQLAlchemy 2 的 Uuid 类型：
  PostgreSQL 上是原生 uuid 列，SQLite 上存 CHAR(32)，生产无缝切换）；
* 两张表都带 org_id / site_id 与通用审计列
  created_at / created_by / updated_at / deleted_at（软删除）；
* started_at / finished_at 改为 DateTime(timezone=True)，不再是字符串。

测试与演示在 SQLite 上跑（零外部依赖）；生产替换点：
    连接串改为 postgresql+psycopg://... 即可，模型与迁移不含任何 SQLite 方言特性。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String, Uuid, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class IpProject(Base):
    __tablename__ = "ip_project"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    org_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    site_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    failed_step: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    failed_segments: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default="system")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class IpJob(Base):
    __tablename__ = "ip_jobs"
    __table_args__ = (
        UniqueConstraint("project_id", "step", "sub_step", name="uq_ip_job_step"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    step: Mapped[str] = mapped_column(String(64))
    sub_step: Mapped[str] = mapped_column(String(64), default="")
    seq: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempt: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    org_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    site_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default="system")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
