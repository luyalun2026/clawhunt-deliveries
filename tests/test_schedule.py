# -*- coding: utf-8 -*-
"""S4-FIN-002 测试套件：验收标准逐条对应 + hypothesis 属性测试。"""
import json
import os
import subprocess
import sys

import pytest
from hypothesis import given, settings, strategies as st

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)
import schedule as sch  # noqa: E402
import reference as ref  # noqa: E402  独立参照算法（与实现写法不同）

PY = sys.executable


def make_event(cid, start, end, cycle, rent_period, rent_total, mem_period=None,
               mem_total=None, deposit=50000, advance=10, first_pay=None):
    fees = [{"fee_type": "rent", "period_amount_cents": rent_period,
             "total_cents": rent_total}]
    if mem_period is not None:
        fees.append({"fee_type": "membership", "period_amount_cents": mem_period,
                     "total_cents": mem_total})
    return {"source_event_id": f"evt-{cid}", "contract_id": cid,
            "company_id": "co-1", "start_date": start, "end_date": end,
            "pay_cycle": cycle, "fees": fees, "deposit_cents": deposit,
            "first_payment_date": first_pay or start, "advance_days": advance}


# ---------- 验收 #1：12 个月季付合同（期望值由参照算法独立给出） ----------

def test_12m_quarter_contract():
    # 2026-01-01~2026-12-31 恰好 4 个完整季度，没有尾期；总额自洽为 4×300000
    ev = make_event("HT-Q1", "2026-01-01", "2026-12-31", "quarter",
                    rent_period=300000, rent_total=1200000,
                    mem_period=90000, mem_total=360000, deposit=50000)
    plan = sch.build_plan(ev)
    rent = [i for i in plan.installments if i.fee_type == "rent"]
    mem = [i for i in plan.installments if i.fee_type == "membership"]
    dep = [i for i in plan.installments if i.fee_type == "deposit"]
    assert len(rent) == 4 and len(mem) == 4 and len(dep) == 1
    assert [i.amount_cents for i in rent] == [300000] * 4
    assert [i.amount_cents for i in mem] == [90000] * 4
    assert all(i.kind == "regular" for i in rent + mem)   # 最后一期是完整周期，不标 tail
    assert sum(i.amount_cents for i in rent) == 1200000
    assert sum(i.amount_cents for i in mem) == 360000
    assert dep[0].amount_cents == 50000 and dep[0].due_date.isoformat() == "2026-01-01"
    assert all(i.amount_cents > 0 for i in plan.installments)
    # 到期日：首期=首付款日，后续=周期开始日-advance_days（4/1 开始 → 3/22 到期）
    assert rent[1].due_date == sch.date(2026, 3, 22)


def test_total_derived_without_declared_total():
    # 本单范围给的 payload 只有周期金额，没有 total_cents → 必须能直接跑出结果
    ev = make_event("HT-NT", "2026-01-01", "2026-12-31", "quarter", 300000, None,
                    deposit=0)
    ev["fees"] = [{"fee_type": "rent", "period_amount_cents": 300000}]
    plan = sch.build_plan(ev)
    assert plan.total_cents == 1200000


def test_tail_proration_day_based():
    # 10 个月季付：3 个完整季 + 31 天尾期（2026-10-01~10-31）
    ev = make_event("HT-T1", "2026-01-01", "2026-10-31", "quarter",
                    rent_period=300000, rent_total=None, deposit=0)
    ev["fees"] = [{"fee_type": "rent", "period_amount_cents": 300000}]
    n_full, tail_days = sch.split_term(sch.date(2026, 1, 1),
                                       sch.date(2026, 10, 31), "quarter")
    assert (n_full, tail_days) == (3, 31)
    plan = sch.build_plan(ev)
    rent = [i for i in plan.installments if i.fee_type == "rent"]
    assert len(rent) == 4 and rent[-1].kind == "tail"
    # 参照值来自 reference.py（整数 divmod 四舍五入），与被测实现的 Decimal 路径无关
    assert rent[-1].amount_cents == ref.tail_amount_cents(300000, 3, 31) == 101918
    assert plan.total_cents == ref.expected_type_total(
        300000, "quarter", sch.date(2026, 1, 1), sch.date(2026, 10, 31))
    assert plan.total_cents == 1001918   # 900000 + 101918，不再被总额截断为 1000000


def test_last_full_period_is_not_tail():
    # 返工点 4：6 个月半年付恰好 1 个完整半年 → 1 期 500000，不标 tail、不重复收取
    ev = make_event("HT-HY", "2026-01-01", "2026-06-30", "half_year",
                    rent_period=500000, rent_total=None, deposit=0)
    ev["fees"] = [{"fee_type": "rent", "period_amount_cents": 500000}]
    plan = sch.build_plan(ev)
    rent = [i for i in plan.installments if i.fee_type == "rent"]
    assert len(rent) == 1 and rent[0].kind == "regular"
    assert rent[0].amount_cents == 500000 and plan.total_cents == 500000


def test_declared_total_absorbs_rounding_only():
    # 声明总额只允许吸收 ≤5 分的舍入尾差
    ev = make_event("HT-TOL", "2026-01-01", "2026-10-31", "quarter",
                    rent_period=300000, rent_total=1001920, deposit=0)   # 差 2 分
    plan = sch.build_plan(ev)
    assert plan.total_cents == 1001920
    assert plan.installments[-1].amount_cents == 101920

    ev_bad = make_event("HT-BAD", "2026-01-01", "2026-10-31", "quarter",
                        rent_period=300000, rent_total=1000000, deposit=0)  # 差 1918 分
    with pytest.raises(sch.FeeTotalMismatch):
        sch.build_plan(ev_bad)


def test_first_year_amount_multi_year():
    ev = make_event("HT-Y2", "2026-01-01", "2027-12-31", "year",
                    rent_period=1200000, rent_total=2400000, deposit=0)
    plan = sch.build_plan(ev)
    assert plan.first_year_amount_cents == 1200000


# ---------- 验收 #2：hypothesis 200 份随机合同（期望值由参照算法独立给出） ----------

CYCLES = st.sampled_from(["month", "quarter", "half_year", "year"])


@st.composite
def contract_strategy(draw):
    """只随机日期/周期/周期金额，期望值全部由 reference.py 独立算出。"""
    from datetime import date, timedelta
    cycle = draw(CYCLES)
    start = date(2026, 1, 1) + timedelta(days=draw(st.integers(0, 300)))
    end = start + timedelta(days=draw(st.integers(30, 1200)) - 1)
    period = draw(st.integers(10000, 500000))
    mem_period = draw(st.integers(1000, 200000))
    deposit = draw(st.integers(0, 100000))
    advance = draw(st.integers(0, 30))
    return {"source_event_id": "evt-h", "contract_id": "HT-H",
            "company_id": "co-1", "start_date": start.isoformat(),
            "end_date": end.isoformat(), "pay_cycle": cycle,
            "fees": [{"fee_type": "rent", "period_amount_cents": period},
                     {"fee_type": "membership", "period_amount_cents": mem_period}],
            "deposit_cents": deposit, "first_payment_date": start.isoformat(),
            "advance_days": advance}


@given(contract_strategy())
@settings(max_examples=200, deadline=None)
def test_hypothesis_200_contracts(ev):
    from datetime import date
    plan = sch.build_plan(ev)
    start, end, cycle = (date.fromisoformat(ev["start_date"]),
                         date.fromisoformat(ev["end_date"]), ev["pay_cycle"])
    for fee in ev["fees"]:
        exp_rows = ref.expected_rows(fee["period_amount_cents"], cycle, start, end)
        got = [(i.kind, i.amount_cents) for i in plan.installments
               if i.fee_type == fee["fee_type"]]
        assert got == [(r[0], r[1]) for r in exp_rows], (fee["fee_type"], cycle, start, end)
        assert sch.by_type(plan, fee["fee_type"]) == sum(r[1] for r in exp_rows)
    assert all(isinstance(i.amount_cents, int) and i.amount_cents > 0
               for i in plan.installments)
    dep = [i for i in plan.installments if i.fee_type == "deposit"]
    assert len(dep) == (1 if ev["deposit_cents"] else 0)


# ---------- 验收 #3：幂等 ----------

def test_idempotent_event_redelivery():
    store = sch.PlanStore()
    ev = make_event("HT-ID1", "2026-01-01", "2026-12-31", "month",
                    100000, 1200000, deposit=20000)
    p1, c1 = store.consume(ev)
    p2, c2 = store.consume(ev)
    p3, c3 = store.consume(ev)
    assert c1 and not c2 and not c3
    assert p1 is p2 is p3


def test_idempotent_same_contract_second_event():
    store = sch.PlanStore()
    ev1 = make_event("HT-ID2", "2026-01-01", "2026-12-31", "month", 100000, 1200000)
    ev2 = dict(ev1, source_event_id="evt-other")
    p1, c1 = store.consume(ev1)
    p2, c2 = store.consume(ev2)
    assert c1 and not c2 and p1 is p2


# ---------- 验收 #4：金额模块无 float ----------

def test_no_float_static_check():
    p = subprocess.run([PY, os.path.join(PKG, "check_no_float.py"), "schedule.py"],
                       capture_output=True, text=True, cwd=PKG, encoding="utf-8")
    assert p.returncode == 0, p.stdout
    assert "违规 0 处" in p.stdout


def test_no_float_checker_detects_violation(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("x = 0.5\ny = float('3')\n", encoding="utf-8")
    p = subprocess.run([PY, os.path.join(PKG, "check_no_float.py"), str(bad)],
                       capture_output=True, text=True, cwd=PKG, encoding="utf-8")
    assert p.returncode == 1
    assert "float" in p.stdout
