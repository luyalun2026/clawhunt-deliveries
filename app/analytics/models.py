"""汇总表模型：page_daily_stats / funnel_daily_stats / monthly_active_companies。

只用 SQLAlchemy 2 的通用类型（Uuid / Date / Integer / String），SQLite 与
PostgreSQL 16 均可直接建表，不使用任何方言私有类型。
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class PageDailyStat(Base):
    __tablename__ = "page_daily_stats"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    stat_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    page: Mapped[str] = mapped_column(String(200), nullable=False)
    pv: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uv: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(64))
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint("stat_date", "site_id", "page", name="uq_page_daily"),
        CheckConstraint("pv >= 0 AND uv >= 0", name="ck_page_daily_nonneg"),
    )


class FunnelDailyStat(Base):
    __tablename__ = "funnel_daily_stats"
    __table_args__ = (
        UniqueConstraint(
            "stat_date", "site_id", "funnel_code", "scope_key", "step_key",
            name="uq_funnel_daily",
        ),
        CheckConstraint("step_index >= 1", name="ck_funnel_step_index"),
        CheckConstraint("user_count >= 0", name="ck_funnel_nonneg"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    stat_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    funnel_code: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False, default="-")
    step_key: Mapped[str] = mapped_column(String(40), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    user_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class MonthlyActiveCompany(Base):
    __tablename__ = "monthly_active_companies"
    __table_args__ = (UniqueConstraint("month", "site_id", "company_pid", name="uq_mac"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    company_pid: Mapped[str] = mapped_column(String(40), nullable=False)
