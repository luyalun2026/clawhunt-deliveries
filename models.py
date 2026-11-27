# -*- coding: utf-8 -*-
"""#2762 会籍表模型（crm/membership）：档位、起止日期与重叠期排他约束。

* PG16：pg_ddl.sql 中 EXCLUDE USING gist（btree_gist），WHERE 谓词
  (deleted_at IS NULL AND status <> 'terminated')；
* SQLite 测试路径：等价 BEFORE INSERT 触发器提供同语义数据库级拒绝。
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    BigInteger, CheckConstraint, Date, DateTime, String, create_engine, text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Membership(Base):
    __tablename__ = "membership"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), nullable=False)
    site_id: Mapped[str | None] = mapped_column(String(36))
    company_id: Mapped[str] = mapped_column(String(36), nullable=False)
    tier: Mapped[str] = mapped_column(String(24), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # NULL=长期有效
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    amount_fen: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    created_by: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("status IN ('active','suspended','terminated','expired')", name="ck_mbr_status"),
        CheckConstraint("tier IN ('standard','premium','corporate')", name="ck_mbr_tier"),
        CheckConstraint("end_date IS NULL OR end_date > start_date", name="ck_mbr_dates"),
    )


SQLITE_OVERLAP_TRIGGER = """
CREATE TRIGGER trg_membership_overlap
BEFORE INSERT ON membership
WHEN NEW.deleted_at IS NULL AND NEW.status <> 'terminated'
BEGIN
  SELECT RAISE(ABORT, 'overlap of active membership ranges')
  WHERE EXISTS (
    SELECT 1 FROM membership old
    WHERE old.id <> NEW.id
      AND old.org_id = NEW.org_id
      AND old.company_id = NEW.company_id
      AND old.deleted_at IS NULL
      AND old.status <> 'terminated'
      AND (old.end_date IS NULL OR old.end_date > NEW.start_date)
      AND (NEW.end_date IS NULL OR NEW.end_date > old.start_date)
  );
END;
"""


def make_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(SQLITE_OVERLAP_TRIGGER))
    return engine


# PG16 EXCLUDE（pg_ddl.sql 同步给出）：
#   CREATE EXTENSION IF NOT EXISTS btree_gist;
#   ALTER TABLE membership ADD CONSTRAINT no_overlap_active_membership
#     EXCLUDE USING gist (org_id WITH =, company_id WITH =,
#       daterange(start_date, COALESCE(end_date,'infinity'::date),'[)') WITH &&)
#     WHERE (deleted_at IS NULL AND status <> 'terminated');
# 模型层元数据同步声明 ExcludeConstraint（autogenerate 不漂移）。
