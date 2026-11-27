# -*- coding: utf-8 -*-
"""#2762 PG16 真库冒烟：EXCLUDE USING gist（需 PG_DSN，无则 skip）。"""
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
        conn.execute(text("DROP TABLE IF EXISTS pg_smoke_membership CASCADE"))
        conn.execute(text("""
            CREATE TABLE pg_smoke_membership (
              id TEXT PRIMARY KEY,
              org_id TEXT NOT NULL, company_id TEXT NOT NULL,
              tier TEXT NOT NULL, start_date DATE NOT NULL, end_date DATE,
              status TEXT NOT NULL DEFAULT 'active',
              amount_fen BIGINT NOT NULL DEFAULT 0,
              deleted_at TIMESTAMPTZ,
              CONSTRAINT no_overlap_active_membership
                EXCLUDE USING gist (org_id WITH =, company_id WITH =,
                  daterange(start_date, COALESCE(end_date,'infinity'::date),'[)') WITH &&)
                WHERE (deleted_at IS NULL AND status <> 'terminated')
            )"""))
    yield engine
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS pg_smoke_membership CASCADE"))
    engine.dispose()


def _ins(engine, company, start, end, status="active"):
    with Session(bind=engine) as s:
        s.execute(text(
            "INSERT INTO pg_smoke_membership (id, org_id, company_id, tier, start_date, end_date, status)"
            " VALUES (gen_random_uuid()::text,'org-pg',:c,'standard',:s,:e,:st)"),
            {"c": company, "s": start, "e": end, "st": status})
        s.commit()


def test_pg_overlap_rejected(pg):
    _ins(pg, "c1", date(2026, 1, 1), date(2026, 6, 30))
    with pytest.raises(Exception):
        _ins(pg, "c1", date(2026, 4, 1), date(2026, 12, 31))


def test_pg_next_day_allowed(pg):
    _ins(pg, "c2", date(2026, 1, 1), date(2026, 6, 30))
    _ins(pg, "c2", date(2026, 7, 1), date(2026, 12, 31))


def test_pg_terminated_release(pg):
    _ins(pg, "c3", date(2026, 1, 1), date(2026, 6, 30))
    with Session(bind=pg) as s:
        s.execute(text("UPDATE pg_smoke_membership SET status='terminated' WHERE company_id='c3'"))
        s.commit()
    _ins(pg, "c3", date(2026, 4, 1), date(2026, 12, 31))  # terminated 释放
