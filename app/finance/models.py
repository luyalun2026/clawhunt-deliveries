"""银行流水导入的数据模型：模板、批次、流水。"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, String,
    UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BankStatementTemplate(Base):
    __tablename__ = "bank_statement_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True,
                                          default=lambda: uuid.uuid4())
    bank_code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    encoding: Mapped[str] = mapped_column(String(20), default="utf-8-sig")
    columns: Mapped[dict] = mapped_column(JSON, nullable=False)
    amount_sign_rule: Mapped[str] = mapped_column(String(20), default="direction")
    date_formats: Mapped[list] = mapped_column(JSON, default=lambda: ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"])
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class BankImportBatch(Base):
    __tablename__ = "bank_import_batches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True,
                                          default=lambda: uuid.uuid4())
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("bank_statement_templates.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(200), default="")
    file_sha256: Mapped[str] = mapped_column(String(64), default="")
    account_no: Mapped[str] = mapped_column(String(40), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    added: Mapped[int] = mapped_column(Integer, default=0)
    skipped_dup: Mapped[int] = mapped_column(Integer, default=0)
    skipped_debit: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    elapsed_ms: Mapped[int] = mapped_column(Integer, default=0)


class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    __table_args__ = (
        UniqueConstraint("account_no", "bank_serial", name="uq_bank_txn"),
        CheckConstraint("status IN ('unmatched','suggested','matched','ignored')", name="ck_txn_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True,
                                          default=lambda: uuid.uuid4())
    batch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("bank_import_batches.id"))
    account_no: Mapped[str] = mapped_column(String(40), nullable=False)
    bank_serial: Mapped[str] = mapped_column(String(64), nullable=False)
    txn_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    counterparty_name: Mapped[str] = mapped_column(String(120), default="")
    counterparty_account: Mapped[str] = mapped_column(String(64), default="")
    memo: Mapped[str] = mapped_column(String(240), default="")
    status: Mapped[str] = mapped_column(String(20), default="unmatched")
