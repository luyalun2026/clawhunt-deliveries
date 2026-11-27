# -*- coding: utf-8 -*-
"""#1964 PG16 专属冒烟测试：EXCLUDE USING gist 互斥（需真实 PostgreSQL 16）。

运行：PG_DSN=postgresql://user:pass@host:5432/db python -m pytest tests/test_pg_smoke.py -q
无 PG_DSN 时整组 skip（SQLite 路径的等价触发器覆盖见 test_quote_rules.py）。
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PG_DSN = os.environ.get("PG_DSN")

pytestmark = pytest.mark.skipif(not PG_DSN, reason="PG_DSN 未设置：需要真实 PostgreSQL 16")


@pytest.fixture(scope="module")
def pg():
    engine = create_engine(PG_DSN)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        conn.execute(text("DROP TABLE IF EXISTS pg_smoke_rule_set CASCADE"))
    from models import Base
    # 仅建 quote_rule_set 一张表用于冒烟
    table = Base.metadata.tables["quote_rule_set"]
    table.create(engine)
    yield engine
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS pg_smoke_rule_set CASCADE"))
    engine.dispose()


def _add(engine, name, vf, vu, status="published"):
    with Session(bind=engine) as s:
        s.execute(text(
            "INSERT INTO quote_rule_set (id, org_id, name, currency, status, valid_from, valid_until, created_at, updated_at)"
            " VALUES (gen_random_uuid()::text, 'org-pg', :name, 'CNY', :status, :vf, :vu, now(), now())"),
            {"name": name, "status": status, "vf": vf, "vu": vu})
        s.commit()


def test_pg_overlap_rejected(pg):
    _add(pg, "冒烟规则", date(2026, 1, 1), date(2026, 6, 30))
    with pytest.raises(Exception):
        _add(pg, "冒烟规则", date(2026, 4, 1), date(2026, 12, 31))


def test_pg_next_day_allowed(pg):
    _add(pg, "冒烟规则2", date(2026, 1, 1), date(2026, 6, 30))
    _add(pg, "冒烟规则2", date(2026, 7, 1), date(2026, 12, 31))  # 次日衔接，成功
