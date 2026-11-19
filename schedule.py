#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""签约事件 → 回款计划分期算法（S4-FIN-002）。

纯函数模块：全程整数分 + Decimal，无 float、无 I/O，便于 hypothesis 属性测试。

事件 payload（contract.signed）：
{
  "source_event_id": "evt-0001",
  "contract_id": "HT-2026-0001",
  "company_id": "co-1",
  "start_date": "2026-01-01", "end_date": "2026-12-31",
  "pay_cycle": "quarter",                  # month | quarter | half_year | year
  "fees": [{"fee_type": "rent", "period_amount_cents": 300000,
            "total_cents": 1200000}],       # total_cents 可省略：缺省按规则推导
  "deposit_cents": 50000,
  "first_payment_date": "2026-01-01",
  "advance_days": 10
}

规则：
  - 每个费用类型的总额 = 完整周期数 × 周期金额 + 尾期按天折算值（由 payload 推导，
    不依赖 total_cents；若业务方另外给出 total_cents，只允许它与推导值的差额在
    ±TOLERANCE_CENTS（5 分）舍入容差内并计入最后一期，超出抛 FeeTotalMismatch）；
  - 每个费用类型：完整周期每周期 1 行，金额 = 周期金额原值（整数分，不做除法）；
    最后一期恰好是完整周期时按周期金额收取，kind='regular'，不标记尾期；
  - 尾期（不足一个完整周期）按天折算：日金额 = 月金额 × 12 ÷ 365
    （月金额 = 周期金额 ÷ 周期月数），Decimal 计算后 ROUND_HALF_UP 取整到 1 分；
  - 到期日：首期 = 首付款日；后续每期 = 周期开始日 − advance_days；
  - 押金独立 1 行，到期日 = 首付款日；
  - 多年合同输出 first_year_amount_cents（起始 12 个月内开始的周期所对应分期金额之和）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

CYCLE_MONTHS = {"month": 1, "quarter": 3, "half_year": 6, "year": 12}
CENT = Decimal("0.01")
# 声明总额与规则推导总额之间允许的最大差额（分）：仅用于吸收四舍五入尾差。
TOLERANCE_CENTS = 5


class FeeTotalMismatch(ValueError):
    """声明总额与规则推导总额相差超过舍入容差。"""


def add_months(d: date, n: int) -> date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    day = min(d.day, [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28,
                      31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return date(y, m, day)


@dataclass
class Installment:
    fee_type: str
    seq: int
    amount_cents: int
    due_date: date
    period_start: date
    period_end: date
    kind: str = "regular"  # regular | tail | deposit


@dataclass
class Plan:
    contract_id: str
    status: str = "active"
    installments: list = field(default_factory=list)
    first_year_amount_cents: int = 0

    @property
    def total_cents(self) -> int:
        return sum(i.amount_cents for i in self.installments)


def _month_amount(period_amount_cents: int, cycle_months: int) -> Decimal:
    """月金额 = 周期金额 ÷ 周期月数（Decimal 真除，保留精度参与折算）。"""
    return Decimal(period_amount_cents) / Decimal(cycle_months)


def _day_amount(period_amount_cents: int, cycle_months: int) -> Decimal:
    """日金额 = 月金额 × 12 ÷ 365（Decimal 真除，取整到分在 prorate_tail 内做）。"""
    return _month_amount(period_amount_cents, cycle_months) * Decimal(12) / Decimal(365)


def prorate_tail(period_amount_cents: int, cycle_months: int, days: int) -> int:
    """尾期按天折算，返回整数分（ROUND_HALF_UP 到 1 分）。

    金额本身以「分」为单位，所以取整单位是 Decimal("1")，不是 CENT。
    """
    raw = _day_amount(period_amount_cents, cycle_months) * Decimal(days)
    return int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def split_term(start: date, end: date, pay_cycle: str) -> tuple[int, int]:
    """拆分合同期：返回 (完整周期数 n_full, 尾期天数 tail_days)。

    完整周期的判据是「周期末 <= 合同期末」；恰好覆盖到期末的那个周期算完整周期，
    不计入尾期。tail_days 为 0 表示没有尾期。
    """
    cm = CYCLE_MONTHS[pay_cycle]
    cursor = start
    n_full = 0
    while True:
        cycle_end = add_months(cursor, cm) - timedelta(days=1)
        if cycle_end > end:
            break
        n_full += 1
        cursor = add_months(cursor, cm)
    tail_days = (end - cursor).days + 1 if cursor <= end else 0
    return n_full, tail_days


def build_fee_installments(fee: dict, start: date, end: date, pay_cycle: str,
                           first_payment_date: date, advance_days: int) -> list:
    """单个费用类型的分期行。

    总额由规则推导：n_full × 周期金额 + 尾期折算；fee["total_cents"] 为可选声明值，
    仅在 ±TOLERANCE_CENTS 内作为舍入尾差并入最后一期，超出抛 FeeTotalMismatch。
    """
    period_amt = int(fee["period_amount_cents"])
    cm = CYCLE_MONTHS[pay_cycle]
    out: list = []
    seq = 0
    cursor = start
    # ① 完整周期：周期末 <= 合同期末，最后一期恰好覆盖到期末时按周期金额收取，不标尾期
    while True:
        cycle_end = add_months(cursor, cm) - timedelta(days=1)
        if cycle_end > end:
            break
        seq += 1
        due = first_payment_date if seq == 1 else cursor - timedelta(days=advance_days)
        out.append(Installment(fee["fee_type"], seq, period_amt, due, cursor, cycle_end))
        cursor = add_months(cursor, cm)
    # ② 尾期：cursor..end 不足一个完整周期，按天折算（这里是唯一可能产生尾期的地方）
    if cursor <= end:
        tail_days = (end - cursor).days + 1
        seq += 1
        due = first_payment_date if seq == 1 else cursor - timedelta(days=advance_days)
        out.append(Installment(fee["fee_type"], seq,
                               prorate_tail(period_amt, cm, tail_days),
                               due, cursor, end, kind="tail"))
    # ③ 与声明总额核对：只容舍入尾差，超差报错而不是静默吸收
    derived = sum(i.amount_cents for i in out)
    if fee.get("total_cents") is not None:
        declared = int(fee["total_cents"])
        delta = declared - derived
        if delta != 0:
            if abs(delta) > TOLERANCE_CENTS:
                raise FeeTotalMismatch(
                    "fee_type=%s 声明总额 %d 分与规则推导 %d 分相差 %d 分，"
                    "超过 ±%d 分舍入容差" % (fee["fee_type"], declared, derived,
                                              delta, TOLERANCE_CENTS))
            out[-1].amount_cents += delta
    return out


def build_plan(event: dict) -> Plan:
    start = date.fromisoformat(event["start_date"])
    end = date.fromisoformat(event["end_date"])
    fpd = date.fromisoformat(event["first_payment_date"])
    adv = int(event.get("advance_days") or 0)
    plan = Plan(contract_id=event["contract_id"])
    for fee in event["fees"]:
        plan.installments.extend(build_fee_installments(
            fee, start, end, event["pay_cycle"], fpd, adv))
    if int(event.get("deposit_cents") or 0) > 0:
        plan.installments.append(Installment(
            "deposit", 1, int(event["deposit_cents"]), fpd, start, start, kind="deposit"))
    first_year_end = add_months(start, 12)
    plan.first_year_amount_cents = sum(
        i.amount_cents for i in plan.installments
        if i.fee_type != "deposit" and i.period_start < first_year_end)
    return plan


def by_type(plan: Plan, fee_type: str) -> int:
    return sum(i.amount_cents for i in plan.installments if i.fee_type == fee_type)


# ---------------------------------------------------------------- 事件消费者（桩）

class PlanStore:
    """幂等存储桩：source_event_id 唯一 + 同合同仅一个 active 计划。

    生产替换点：实现为 PostgreSQL 表（source_event_id 唯一索引 +
    (contract_id, status='active') 部分唯一索引），接口不变。
    """

    def __init__(self):
        self._by_event: dict[str, Plan] = {}
        self._active_by_contract: dict[str, Plan] = {}

    def consume(self, event: dict) -> tuple[Plan, bool]:
        """返回 (计划, 是否新生成)。重复投递返回既有计划且 created=False。"""
        eid = event["source_event_id"]
        if eid in self._by_event:
            return self._by_event[eid], False
        cid = event["contract_id"]
        if cid in self._active_by_contract:
            plan = self._active_by_contract[cid]
            self._by_event[eid] = plan
            return plan, False
        plan = build_plan(event)
        self._by_event[eid] = plan
        self._active_by_contract[cid] = plan
        return plan, True


def load_event(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
