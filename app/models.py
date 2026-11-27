# -*- coding: utf-8 -*-
"""S6-POD-040 数据模型（SQLAlchemy 2，方言中立：PG16 用 JSONB/UUID，SQLite 测试自动降级）。"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer,
    String, UniqueConstraint, create_engine, func, select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

try:  # 生产 PostgreSQL 16
    from sqlalchemy.dialects.postgresql import JSONB as JSON_TYPE
    from sqlalchemy.dialects.postgresql import UUID as UUID_TYPE
except ImportError:  # 测试 SQLite
    from sqlalchemy import JSON as JSON_TYPE
    from sqlalchemy import String as UUID_TYPE


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


def _uuid_col():
    return mapped_column(UUID_TYPE(as_uuid=False), primary_key=True, default=gen_uuid)


class Episode(Base):
    """节目元数据（虚构测试数据）。"""
    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    column_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200))
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 缺失 → NULL


class ListeningEvent(Base):
    """收听事件流水。event_type: episode_view / play_start / progress / complete"""
    __tablename__ = "listening_events"

    id: Mapped[str] = _uuid_col()
    org_id: Mapped[str] = mapped_column(String(64), default="org_demo", index=True)
    site_id: Mapped[str] = mapped_column(String(64), default="site_demo")
    episode_id: Mapped[str] = mapped_column(String(64), ForeignKey("episodes.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    anon_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="unknown")
    played_delta_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EpisodeDailyStats(Base):
    """节目 × 日期 汇总（episode_id='__ALL__' 为全站汇总行）。"""
    __tablename__ = "episode_daily_stats"
    __table_args__ = (UniqueConstraint("org_id", "episode_id", "stat_date",
                                       name="ux_episode_daily"),)

    id: Mapped[str] = _uuid_col()
    org_id: Mapped[str] = mapped_column(String(64), index=True)
    site_id: Mapped[str] = mapped_column(String(64), default="site_demo")
    episode_id: Mapped[str] = mapped_column(String(64), index=True)
    column_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    stat_date: Mapped[date] = mapped_column(Date, index=True)
    views: Mapped[int] = mapped_column(BigInteger, default=0)
    plays: Mapped[int] = mapped_column(BigInteger, default=0)
    unique_listeners: Mapped[int] = mapped_column(BigInteger, default=0)
    listen_seconds: Mapped[int] = mapped_column(BigInteger, default=0)
    completes: Mapped[int] = mapped_column(BigInteger, default=0)
    completion_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_listen_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    reach_10: Mapped[int] = mapped_column(BigInteger, default=0)
    reach_20: Mapped[int] = mapped_column(BigInteger, default=0)
    reach_30: Mapped[int] = mapped_column(BigInteger, default=0)
    reach_40: Mapped[int] = mapped_column(BigInteger, default=0)
    reach_50: Mapped[int] = mapped_column(BigInteger, default=0)
    reach_60: Mapped[int] = mapped_column(BigInteger, default=0)
    reach_70: Mapped[int] = mapped_column(BigInteger, default=0)
    reach_80: Mapped[int] = mapped_column(BigInteger, default=0)
    reach_90: Mapped[int] = mapped_column(BigInteger, default=0)
    reach_100: Mapped[int] = mapped_column(BigInteger, default=0)
    source_breakdown: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ColumnDailyStats(Base):
    """栏目 × 日期 汇总。"""
    __tablename__ = "column_daily_stats"
    __table_args__ = (UniqueConstraint("org_id", "column_id", "stat_date",
                                       name="ux_column_daily"),)

    id: Mapped[str] = _uuid_col()
    org_id: Mapped[str] = mapped_column(String(64), index=True)
    site_id: Mapped[str] = mapped_column(String(64), default="site_demo")
    column_id: Mapped[str] = mapped_column(String(64), index=True)
    stat_date: Mapped[date] = mapped_column(Date, index=True)
    views: Mapped[int] = mapped_column(BigInteger, default=0)
    plays: Mapped[int] = mapped_column(BigInteger, default=0)
    unique_listeners: Mapped[int] = mapped_column(BigInteger, default=0)
    listen_seconds: Mapped[int] = mapped_column(BigInteger, default=0)
    completes: Mapped[int] = mapped_column(BigInteger, default=0)
    completion_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
