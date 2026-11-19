# -*- coding: utf-8 -*-
"""独立参照算法（不 import schedule，用于交叉验证）。

与生产实现的差异：
  · 周期边界用 (年, 月) 元组递推，不用 add_months 的按月加法函数；
  · 尾期折算用整数 divmod 做 ROUND_HALF_UP，不用 Decimal；
  · 总额恒由规则推导，不读 total_cents。
这些差异保证「参照值 != 被测代码的自证值」：若实现写错，这里不会跟着错。
"""
from __future__ import annotations

from datetime import date, timedelta

_MONTH_LEN = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
_CYCLE = {"month": 1, "quarter": 3, "half_year": 6, "year": 12}


def _is_leap(y: int) -> bool:
    return (y % 4 == 0 and y % 100 != 0) or y % 400 == 0


def _days_in_month(y: int, m: int) -> int:
    return 29 if (m == 2 and _is_leap(y)) else _MONTH_LEN[m - 1]


def _shift(d: date, months: int) -> date:
    """从 (y, m) 元组递推 months 个月，日取 min(d.day, 当月天数)。"""
    idx = (d.year * 12 + (d.month - 1)) + months
    y, m = idx // 12, idx % 12 + 1
    return date(y, m, min(d.day, _days_in_month(y, m)))


def _round_half_up(num: int, den: int) -> int:
    """整数除法 ROUND_HALF_UP：num/den 四舍五入到整数。num、den 均为正。"""
    q, r = divmod(num, den)
    if r * 2 >= den:
        q += 1
    return q


def tail_amount_cents(period_cents: int, cycle_months: int, days: int) -> int:
    """日金额 = 月金额 × 12 ÷ 365 = period × 12 ÷ (cycle_months × 365)。"""
    return _round_half_up(period_cents * 12 * days, cycle_months * 365)


def expected_rows(period_cents: int, cycle: str, start: date, end: date) -> list:
    """返回 [(kind, amount_cents, period_start, period_end), ...]。"""
    cm = _CYCLE[cycle]
    rows = []
    cursor = start
    while True:
        cycle_end = _shift(cursor, cm) - timedelta(days=1)
        if cycle_end > end:
            break
        rows.append(("regular", period_cents, cursor, cycle_end))
        cursor = _shift(cursor, cm)
    if cursor <= end:
        days = (end - cursor).days + 1
        rows.append(("tail", tail_amount_cents(period_cents, cm, days), cursor, end))
    return rows


def expected_type_total(period_cents: int, cycle: str, start: date, end: date) -> int:
    return sum(r[1] for r in expected_rows(period_cents, cycle, start, end))


if __name__ == "__main__":
    # 自检：三个被返工点名的样例
    d = date
    print("01 12m quarter:", expected_type_total(300000, "quarter", d(2026, 1, 1), d(2026, 12, 31)),
          "期望 1200000")
    print("03 10m quarter:", expected_type_total(300000, "quarter", d(2026, 1, 1), d(2026, 10, 31)),
          "尾期 31 天 期望尾值 101918")
    print("05 6m half_year:", expected_type_total(500000, "half_year", d(2026, 1, 1), d(2026, 6, 30)),
          "期望 500000")
