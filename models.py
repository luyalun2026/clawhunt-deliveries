# -*- coding: utf-8 -*-
"""#2288 v2 · SQLAlchemy 2 模型（统一技术约定：SQLAlchemy 2 / Alembic / PostgreSQL 16）。

测试与演示在 SQLite 上跑（零外部依赖）；生产替换点：
    连接串改为 postgresql+psycopg://... 即可，模型与迁移不含任何 SQLite 方言特性。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IpProject(Base):
    __tablename__ = "ip_project"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    failed_step: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    failed_segments: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)


class IpJob(Base):
    __tablename__ = "ip_jobs"
    __table_args__ = (
        UniqueConstraint("project_id", "step", "sub_step", name="uq_ip_job_step"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    step: Mapped[str] = mapped_column(String(64))
    sub_step: Mapped[str] = mapped_column(String(64), default="")
    seq: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    finished_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    org_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    site_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
