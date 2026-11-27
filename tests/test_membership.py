# -*- coding: utf-8 -*-
"""#2762 验收测试（SQLite 等价触发器路径；PG16 真库冒烟 test_pg_smoke.py）。

AC2 重叠拒绝 + 次日衔接；AC3 terminated / 软删除双路径释放；
AC4 end_date < start_date 被 CHECK 拒绝；边界：跨企业不互斥、长期有效参与排他。
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models import Membership, make_engine


def _fresh() -> Session:
    return Session(bind=make_engine())


def _add(s, company, start, end, status="active", org="org-1"):
    m = Membership(org_id=org, company_id=company, tier="standard",
                   start_date=start, end_date=end, status=status,
                   amount_fen=120000)
    s.add(m)
    return m


# ---------------------------------------------------------------- AC2
def test_ac2_overlap_rejected():
    s = _fresh()
    _add(s, "company-1", date(2026, 1, 1), date(2026, 6, 30))
    s.commit()
    _add(s, "company-1", date(2026, 4, 1), date(2026, 12, 31))  # 重叠
    with pytest.raises(Exception) as ei:
        s.commit()
    assert "overlap" in str(ei.value).lower()


def test_ac2_next_day_adjacent_allowed():
    s = _fresh()
    _add(s, "company-1", date(2026, 1, 1), date(2026, 6, 30))
    s.commit()
    _add(s, "company-1", date(2026, 7, 1), date(2026, 12, 31))  # 次日衔接
    s.commit()
    n = s.execute(select(func.count()).select_from(Membership)).scalar()
    assert n == 2


# ---------------------------------------------------------------- AC3
def test_ac3_terminated_release():
    s = _fresh()
    first = _add(s, "company-1", date(2026, 1, 1), date(2026, 12, 31))
    s.commit()
    first.status = "terminated"
    s.commit()
    _add(s, "company-1", date(2026, 6, 1), date(2026, 12, 31))  # 重叠区间
    s.commit()  # terminated 释放后可插入
    n = s.execute(select(func.count()).select_from(Membership)).scalar()
    assert n == 2


def test_ac3_soft_delete_release():
    s = _fresh()
    first = _add(s, "company-1", date(2026, 1, 1), date(2026, 12, 31))
    s.commit()
    first.deleted_at = datetime.now(timezone.utc)
    s.commit()
    _add(s, "company-1", date(2026, 6, 1), date(2026, 12, 31))
    s.commit()  # 软删除释放后可插入
    n = s.execute(select(func.count()).select_from(Membership)).scalar()
    assert n == 2


# ---------------------------------------------------------------- AC4
def test_ac4_end_before_start_rejected():
    s = _fresh()
    _add(s, "company-1", date(2026, 6, 1), date(2026, 1, 1))  # end < start
    with pytest.raises(IntegrityError):
        s.commit()
    s.rollback()


# ---------------------------------------------------------------- 边界
def test_boundary_cross_company_not_exclusive():
    s = _fresh()
    _add(s, "company-1", date(2026, 1, 1), date(2026, 12, 31))
    s.commit()
    _add(s, "company-2", date(2026, 1, 1), date(2026, 12, 31))  # 不同企业
    s.commit()
    n = s.execute(select(func.count()).select_from(Membership)).scalar()
    assert n == 2


def test_boundary_open_end_participates():
    """长期有效（end_date NULL）与新会籍重叠被拒。"""
    s = _fresh()
    _add(s, "company-1", date(2026, 1, 1), None)  # 长期有效
    s.commit()
    _add(s, "company-1", date(2026, 6, 1), date(2026, 12, 31))
    with pytest.raises(Exception):
        s.commit()


def test_boundary_bad_status_rejected():
    s = _fresh()
    m = Membership(org_id="o", company_id="c", tier="standard",
                   start_date=date(2026, 1, 1), end_date=None,
                   status="frozen", amount_fen=0)  # 非法枚举
    s.add(m)
    with pytest.raises(IntegrityError):
        s.commit()
    s.rollback()
