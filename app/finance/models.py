"""科目映射、导出审计、期间锁定与导出快照。"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint,
    Uuid, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AccountingMapping(Base):
    __tablename__ = "accounting_mappings"
    __table_args__ = (UniqueConstraint("fee_type", name="uq_fee_type"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True,
                                          default=lambda: uuid.uuid4())
    fee_type: Mapped[str] = mapped_column(String(40), nullable=False)
    revenue_account: Mapped[str] = mapped_column(String(20), nullable=False)
    receivable_account: Mapped[str] = mapped_column(String(20), nullable=False)
    tax_account: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExportRun(Base):
    __tablename__ = "export_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True,
                                          default=lambda: uuid.uuid4())
    period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    export_type: Mapped[str] = mapped_column(String(20), nullable=False)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    total_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    file_sha256: Mapped[str] = mapped_column(String(64), default="")
    operator: Mapped[str] = mapped_column(String(40), default="system")
    is_adjustment: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class PeriodLock(Base):
    __tablename__ = "period_locks"

    period: Mapped[str] = mapped_column(String(7), primary_key=True)
    first_exported_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class ExportSnapshot(Base):
    __tablename__ = "export_snapshots"
    __table_args__ = (UniqueConstraint("period", "export_type", "row_key", name="uq_snapshot_row"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True,
                                          default=lambda: uuid.uuid4())
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    export_type: Mapped[str] = mapped_column(String(20), nullable=False)
    row_key: Mapped[str] = mapped_column(String(120), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
