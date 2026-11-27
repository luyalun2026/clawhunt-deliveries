# -*- coding: utf-8 -*-
"""#1964 验收测试（SQLite 测试路径；PG16 专属用例见 test_pg_smoke.py）。

AC1 迁移往返与 alembic check：见 migrations/ + README 命令；本文件覆盖：
  AC2 同名规则表 published 生效区间重叠被数据库拒绝（SQLite 等价触发器路径）
  AC3 member_company_id 与 prospect_name 同空/同有值写入失败
  AC4 种子导入后 quote_rule_item 恰 12 行（+阶梯 2 组、折扣 3 条）
边界：次日衔接、draft 重叠放行、软删除释放、discount_bp 越界。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import seed as seed_mod
from models import (Quote, QuoteDiscountRule, QuoteRuleItem, QuoteRuleSet,
                    make_engine)


@pytest.fixture()
def session():
    engine = make_engine()
    from sqlalchemy.orm import Session as _S
    s = _S(bind=engine)
    yield s
    s.close()


def _published(session, name, vf, vu, status="published", org="org-1"):
    rs = QuoteRuleSet(name=name, currency="CNY", status=status,
                      valid_from=vf, valid_until=vu, org_id=org)
    session.add(rs)
    return rs


def _fresh():
    """独立引擎 + Session（触发器/约束测试需隔离库）。"""
    from sqlalchemy.orm import Session as _S
    return _S(bind=make_engine())


# ---------------------------------------------------------------- AC2
def test_ac2_overlap_rejected_by_database():
    """AC2：同 org 同名两条 published 区间重叠，数据库层拒绝。"""
    s2 = _fresh()
    _published(s2, "规则A", date(2026, 1, 1), date(2026, 6, 30))
    s2.commit()
    _published(s2, "规则A", date(2026, 4, 1), date(2026, 12, 31))  # 重叠
    with pytest.raises(Exception) as ei:
        s2.commit()
    assert "overlap" in str(ei.value).lower()
    s2.rollback()


def test_ac2_next_day_adjacent_allowed():
    """边界：前版 valid_until 与新版 valid_from 次日衔接，不重叠，可插入。"""
    s2 = _fresh()
    _published(s2, "规则A", date(2026, 1, 1), date(2026, 6, 30))
    s2.commit()
    _published(s2, "规则A", date(2026, 7, 1), date(2026, 12, 31))  # 次日衔接
    s2.commit()  # 不抛异常即通过
    n = s2.execute(select(func.count()).select_from(QuoteRuleSet)).scalar()
    assert n == 2


def test_ac2_draft_overlap_allowed():
    """边界：draft 版本重叠不受互斥限制。"""
    s2 = _fresh()
    _published(s2, "规则B", date(2026, 1, 1), date(2026, 6, 30))
    s2.commit()
    _published(s2, "规则B", date(2026, 3, 1), date(2026, 9, 30), status="draft")
    s2.commit()  # draft 放行
    n = s2.execute(select(func.count()).select_from(QuoteRuleSet)).scalar()
    assert n == 2


def test_ac2_soft_deleted_releases_range():
    """边界：published 软删除后区间释放，可插入重叠版本。"""
    s2 = _fresh()
    first = _published(s2, "规则C", date(2026, 1, 1), date(2026, 12, 31))
    s2.commit()
    from datetime import datetime, timezone
    first.deleted_at = datetime.now(timezone.utc)
    s2.commit()
    _published(s2, "规则C", date(2026, 6, 1), date(2026, 12, 31))
    s2.commit()  # 软删除释放后放行
    n = s2.execute(select(func.count()).select_from(QuoteRuleSet)).scalar()
    assert n == 2


# ---------------------------------------------------------------- AC3
@pytest.mark.parametrize("company,prospect", [(None, None), ("company-1", "意向客户甲")])
def test_ac3_xor_fields_rejected(company, prospect):
    """AC3：member_company_id 与 prospect_name 同空或同有值，写入失败。"""
    s2 = _fresh()
    rs = _published(s2, "规则D", date(2026, 1, 1), date(2026, 12, 31))
    s2.commit()
    q = Quote(quote_no="Q-001", member_company_id=company, prospect_name=prospect,
              rule_set_id=rs.id, rule_version="v1", org_id="org-1",
              subtotal_fen=0, discount_fen=0, tax_fen=0, total_fen=0, calc_trace={})
    s2.add(q)
    with pytest.raises(IntegrityError):
        s2.commit()
    s2.rollback()


def test_ac3_xor_either_side_ok():
    """AC3 反例：任一侧单独有值即可写入。"""
    s2 = _fresh()
    rs = _published(s2, "规则E", date(2026, 1, 1), date(2026, 12, 31))
    s2.commit()
    q1 = Quote(quote_no="Q-101", member_company_id="company-1", prospect_name=None,
               rule_set_id=rs.id, rule_version="v1", org_id="org-1",
               subtotal_fen=1000, discount_fen=0, tax_fen=0, total_fen=1000, calc_trace={})
    q2 = Quote(quote_no="Q-102", member_company_id=None, prospect_name="意向客户甲",
               rule_set_id=rs.id, rule_version="v1", org_id="org-1",
               subtotal_fen=2000, discount_fen=0, tax_fen=0, total_fen=2000, calc_trace={})
    s2.add_all([q1, q2])
    s2.commit()
    n = s2.execute(select(func.count()).select_from(Quote)).scalar()
    assert n == 2


# ---------------------------------------------------------------- AC4
def test_ac4_seed_counts():
    """AC4：种子导入后 quote_rule_item 恰 12 行、阶梯价 2 组、折扣 3 条。"""
    s2 = _fresh()
    seed_mod.seed(s2)
    items = s2.execute(select(QuoteRuleItem)).scalars().all()
    assert len(items) == 12, len(items)
    tiered = [i for i in items if i.price_mode == "tiered"]
    assert len(tiered) == seed_mod.TIERED_COUNT == 2
    discounts = s2.execute(select(QuoteDiscountRule)).scalars().all()
    assert len(discounts) == 3
    assert {d.type for d in discounts} == {"member_level", "term_months", "bundle"}


def test_ac4_discount_bp_out_of_range_rejected():
    """边界：discount_bp 越界（>10000）被 CHECK 拒绝。"""
    s2 = _fresh()
    rs = _published(s2, "规则F", date(2026, 1, 1), date(2026, 12, 31))
    s2.commit()
    s2.add(QuoteDiscountRule(rule_set_id=rs.id, org_id="org-1", type="member_level",
                             condition={"level": "x"}, discount_bp=12000, stackable=False))
    with pytest.raises(IntegrityError):
        s2.commit()
    s2.rollback()
