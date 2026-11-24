"""episode_conversion_stats：每期节目的对接请求与转化归因日汇总。"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Date, DateTime, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EpisodeConversionStat(Base):
    __tablename__ = "episode_conversion_stats"
    __table_args__ = (UniqueConstraint("episode_id", "stat_date", name="uq_episode_stats"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True,
                                          default=lambda: uuid.uuid4())
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    episode_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    stat_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    intro_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    intro_staff_approved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    intro_accepted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assisted_event_signups: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assisted_course_signups: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assisted_opportunity_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
