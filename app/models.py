"""llm_call_log 的 SQLAlchemy 2 模型（统一技术约定：SQLAlchemy 2 / PostgreSQL 16）。

生产库为 PostgreSQL 16；测试与单机运行用 store.CallLogStore（SQLite 同构表），
两套字段一致，切换只换连接串。字段与 store.py 的 DDL 逐列对应。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class LlmCallLog(Base):
    __tablename__ = "llm_call_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    field_group: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    parse_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def public(self) -> dict:
        return {
            "id": self.id,
            "field_group": self.field_group,
            "prompt_version": self.prompt_version,
            "model": self.model,
            "attempt": self.attempt,
            "parse_ok": self.parse_ok,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
