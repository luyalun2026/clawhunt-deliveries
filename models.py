# -*- coding: utf-8 -*-
"""#1964 报价规则表与报价单数据模型（SQLAlchemy 2）。

约定：统一业务列（id UUID、org_id、site_id、created_at、created_by、updated_at、
deleted_at 软删除）；金额一律 bigint 分；比例一律整数基点（bp）。

同名规则表的 published 版本生效区间互斥约束：
* PostgreSQL：pg_ddl.sql / Alembic 迁移中的 EXCLUDE USING gist（btree_gist）；
* SQLite 测试路径：等价 BEFORE INSERT 触发器（trg_quote_rule_set_overlap），
  在测试库上提供同语义的数据库级拒绝。
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON, BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey,
    Integer, String, Text, create_engine, event, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TenancyMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    site_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    created_by: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QuoteRuleSet(TenancyMixin, Base):
    """报价规则集：同一 rule 的 published 版本生效区间不得重叠。"""
    __tablename__ = "quote_rule_set"
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    __table_args__ = (
        CheckConstraint("status IN ('draft','published','retired')", name="ck_qrs_status"),
    )


class QuoteRuleItem(TenancyMixin, Base):
    """服务项行：fixed 或 tiered（阶梯价）。金额 bigint 分。"""
    __tablename__ = "quote_rule_item"
    rule_set_id: Mapped[str] = mapped_column(String(36), ForeignKey("quote_rule_set.id"), nullable=False, index=True)
    service_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    price_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    qty_from: Mapped[int | None] = mapped_column(Integer)
    qty_to: Mapped[int | None] = mapped_column(Integer)
    unit_price_fen: Mapped[int] = mapped_column(BigInteger, nullable=False)
    __table_args__ = (
        CheckConstraint("price_mode IN ('fixed','tiered')", name="ck_qri_mode"),
        CheckConstraint("unit_price_fen >= 0", name="ck_qri_price"),
        CheckConstraint("qty_from IS NULL OR qty_to IS NULL OR qty_from <= qty_to", name="ck_qri_qty"),
    )


class QuoteDiscountRule(TenancyMixin, Base):
    """折扣规则：整数基点（bp），cap_bp 上限。"""
    __tablename__ = "quote_discount_rule"
    rule_set_id: Mapped[str] = mapped_column(String(36), ForeignKey("quote_rule_set.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(24), nullable=False)
    condition: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)
    discount_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    stackable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cap_bp: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (
        CheckConstraint("type IN ('member_level','term_months','bundle')", name="ck_qdr_type"),
        CheckConstraint("discount_bp >= 0 AND discount_bp <= 10000", name="ck_qdr_bp"),
        CheckConstraint("cap_bp IS NULL OR (cap_bp >= 0 AND cap_bp <= 10000)", name="ck_qdr_cap"),
    )


class Quote(TenancyMixin, Base):
    """报价单：member_company_id 与 prospect_name 二选一（AC3）。"""
    __tablename__ = "quote"
    quote_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    member_company_id: Mapped[str | None] = mapped_column(String(36), index=True)
    prospect_name: Mapped[str | None] = mapped_column(String(128))
    rule_set_id: Mapped[str] = mapped_column(String(36), ForeignKey("quote_rule_set.id"), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    valid_until: Mapped[date | None] = mapped_column(Date)
    subtotal_fen: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    discount_fen: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_fen: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_fen: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    calc_trace: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict)
    __table_args__ = (
        CheckConstraint("(member_company_id IS NULL) <> (prospect_name IS NULL)", name="ck_quote_xor"),
        CheckConstraint("status IN ('draft','pending_approval','approved','sent','expired','void')", name="ck_quote_status"),
    )


class QuoteLine(TenancyMixin, Base):
    __tablename__ = "quote_line"
    quote_id: Mapped[str] = mapped_column(String(36), ForeignKey("quote.id"), nullable=False, index=True)
    item_code: Mapped[str] = mapped_column(String(64), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_fen: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_subtotal_fen: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_discount_fen: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_tax_fen: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    line_total_fen: Mapped[int] = mapped_column(BigInteger, nullable=False)
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_ql_qty"),
        CheckConstraint("line_total_fen = line_subtotal_fen - line_discount_fen + line_tax_fen", name="ck_ql_math"),
    )


SQLITE_OVERLAP_TRIGGER = """
CREATE TRIGGER trg_quote_rule_set_overlap
BEFORE INSERT ON quote_rule_set
WHEN NEW.status = 'published' AND NEW.deleted_at IS NULL
BEGIN
    SELECT RAISE(ABORT, 'overlap of published rule_set ranges')
    WHERE EXISTS (
      SELECT 1 FROM quote_rule_set old
      WHERE old.id <> NEW.id
        AND old.status = 'published'
        AND old.deleted_at IS NULL
        AND old.org_id = NEW.org_id
        AND old.name = NEW.name
        AND (old.valid_until IS NULL OR old.valid_until > NEW.valid_from)
        AND (NEW.valid_until IS NULL OR NEW.valid_until > old.valid_from)
    );
END;
"""


def make_engine(sqlite_memory: bool = True):
    """创建测试引擎；SQLite 路径附带等价重叠触发器。"""
    if sqlite_memory:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    else:
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(SQLITE_OVERLAP_TRIGGER))
    return engine
