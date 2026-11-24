"""calib.health_snapshot：健康分校准特征快照。

schema 名由环境变量 CALIB_SCHEMA 控制（生产 = calib，测试置空以适配 SQLite）。

约束分层：
- 数据库 CHECK：数值区间、枚举、非负（SQLite / PostgreSQL 16 通用写法）。
- 业务校验：snapshot_date 必须是每月 1 日、industry_code 必须符合 GB/T 4754-2017
  的「门类字母 + 大类两位」，在 `validators.validate_row()` 中实现（跨库一致，
  且错误信息可读），写入前强制调用。
"""
from __future__ import annotations

import datetime as dt
import os
import re

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = os.environ.get("CALIB_SCHEMA", "calib")
TABLE_ARGS: list = [
    UniqueConstraint("snapshot_date", "company_pid", name="uq_health_snapshot"),
    CheckConstraint("tenure_days >= 0", name="ck_tenure_nonneg"),
    CheckConstraint("health_score IS NULL OR (health_score >= 0 AND health_score <= 100)",
                    name="ck_health_score_range"),
    CheckConstraint("health_level IS NULL OR health_level IN ('A','B','C','D')",
                    name="ck_health_level"),
    CheckConstraint("event_score IS NULL OR (event_score >= 0 AND event_score <= 100)",
                    name="ck_event_score_range"),
    CheckConstraint("interaction_score IS NULL OR (interaction_score >= 0 AND interaction_score <= 100)",
                    name="ck_interaction_score_range"),
    CheckConstraint("resource_score IS NULL OR (resource_score >= 0 AND resource_score <= 100)",
                    name="ck_resource_score_range"),
    CheckConstraint("opportunity_score IS NULL OR (opportunity_score >= 0 AND opportunity_score <= 100)",
                    name="ck_opportunity_score_range"),
    CheckConstraint("space_score IS NULL OR (space_score >= 0 AND space_score <= 100)",
                    name="ck_space_score_range"),
]
if SCHEMA:
    TABLE_ARGS.append({"schema": SCHEMA})


class Base(DeclarativeBase):
    pass


class HealthSnapshot(Base):
    __tablename__ = "health_snapshot"
    __table_args__ = tuple(TABLE_ARGS)

    # 维度组
    snapshot_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    company_pid: Mapped[str] = mapped_column(String(40), primary_key=True)
    site_code: Mapped[str] = mapped_column(String(20), nullable=False)
    industry_code: Mapped[str] = mapped_column(String(8), nullable=False)
    stage: Mapped[str] = mapped_column(String(20), nullable=False)
    membership_level: Mapped[str] = mapped_column(String(20), nullable=False)
    tenure_days: Mapped[int] = mapped_column(Integer, nullable=False)
    days_to_expiry: Mapped[int] = mapped_column(Integer, nullable=False)

    # 子项原始值
    event_raw: Mapped[int | None] = mapped_column(Integer)
    interaction_raw: Mapped[int | None] = mapped_column(Integer)
    resource_raw: Mapped[int | None] = mapped_column(Integer)
    opportunity_raw: Mapped[int | None] = mapped_column(Integer)
    space_raw: Mapped[float | None] = mapped_column(Numeric(10, 2))

    # 子项标准化分
    event_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    interaction_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    resource_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    opportunity_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    space_score: Mapped[float | None] = mapped_column(Numeric(5, 2))

    # 汇总与系统列
    health_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    health_level: Mapped[str | None] = mapped_column(String(20))
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    algorithm_version: Mapped[str] = mapped_column(String(20), default="v1")


# 业务字段 18 个（维度 8 + 原始 5 + 标准化 5），汇总与系统列 4 个
BUSINESS_FIELDS = [
    "snapshot_date", "company_pid", "site_code", "industry_code", "stage",
    "membership_level", "tenure_days", "days_to_expiry",
    "event_raw", "interaction_raw", "resource_raw", "opportunity_raw", "space_raw",
    "event_score", "interaction_score", "resource_score", "opportunity_score", "space_score",
]
SYSTEM_FIELDS = ["health_score", "health_level", "computed_at", "algorithm_version"]

INDUSTRY_RE = re.compile(r"^[A-Z][0-9]{2}$")


def validate_row(row: dict) -> list[str]:
    """写入前的业务校验，返回错误清单（空表示通过）。"""
    errors: list[str] = []
    d = row.get("snapshot_date")
    if isinstance(d, str):
        d = dt.date.fromisoformat(d)
    if d is None:
        errors.append("snapshot_date 缺失")
    elif d.day != 1:
        errors.append(f"snapshot_date 必须是每月 1 日，实际 {d.isoformat()}")
    code = row.get("industry_code") or ""
    if not INDUSTRY_RE.match(code):
        errors.append(f"industry_code 不符合 GB/T 4754-2017 门类+大类格式：{code!r}")
    if (row.get("tenure_days") or 0) < 0:
        errors.append("tenure_days 不得为负")
    score = row.get("health_score")
    if score is not None and not (0 <= float(score) <= 100):
        errors.append(f"health_score 越界：{score}")
    level = row.get("health_level")
    if level is not None and level not in ("A", "B", "C", "D"):
        errors.append(f"health_level 非枚举值：{level!r}")
    for key in ("event_score", "interaction_score", "resource_score",
                "opportunity_score", "space_score"):
        value = row.get(key)
        if value is not None and not (0 <= float(value) <= 100):
            errors.append(f"{key} 越界：{value}")
    return errors
