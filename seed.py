# -*- coding: utf-8 -*-
"""#1964 种子数据：12 个服务项、2 档阶梯价、3 条折扣规则。

导入后 quote_rule_item 恰 12 行（AC4）；阶梯价 2 组（各两档）；折扣 3 条
（member_level / term_months / bundle 各一）。
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from models import QuoteDiscountRule, QuoteRuleItem, QuoteRuleSet

RULE_SET_NAME = "种子规则集 2026Q1"
VALID_FROM = date(2026, 1, 1)
VALID_UNTIL = date(2026, 12, 31)

SERVICES = [
    # (service_code, name, price_mode, qty_from, qty_to, unit_price_fen)
    ("MEET-L", "大型会议室 · 全天", "fixed", None, None, 80000),
    ("MEET-S", "小型会议室 · 半天", "fixed", None, None, 30000),
    ("DESK-F", "固定工位 · 月", "fixed", None, None, 120000),
    ("DESK-H", "灵活工位 · 日", "fixed", None, None, 6000),
    ("ADDR-REG", "注册地址挂靠 · 年", "fixed", None, None, 240000),
    ("PRINT-BW", "黑白打印 · 页", "fixed", None, None, 15),
    ("PRINT-CL", "彩色打印 · 页", "fixed", None, None, 50),
    ("EVT-HALL", "活动厅 · 场", "fixed", None, None, 200000),
    ("VIP-ROOM", "VIP 接待室 · 小时", "fixed", None, None, 15000),
    ("STOR-S", "小仓柜 · 月", "fixed", None, None, 9000),
    ("NET-D", "专线带宽 · 天", "tiered", 1, 9, 30000),
    ("NET-M", "专线带宽 · 月（阶梯）", "tiered", 10, None, 25000),
]
TIERED_COUNT = 2  # NET-D / NET-M


def seed(session: Session) -> dict:
    rs = QuoteRuleSet(name=RULE_SET_NAME, currency="CNY", status="published",
                      valid_from=VALID_FROM, valid_until=VALID_UNTIL,
                      org_id="seed-org")
    session.add(rs)
    session.flush()

    for code, name, mode, qf, qt, price in SERVICES:
        session.add(QuoteRuleItem(rule_set_id=rs.id, org_id="seed-org",
                                  service_code=code, name=name, price_mode=mode,
                                  qty_from=qf, qty_to=qt, unit_price_fen=price))

    discounts = [
        ("member_level", {"level": "gold"}, 500, True, None),      # 5%
        ("term_months", {"min_months": 12}, 800, False, 1000),     # 8%，上限 10%
        ("bundle", {"codes": ["DESK-F", "MEET-S"]}, 300, True, 500),
    ]
    for dtype, cond, bp, stack, cap in discounts:
        session.add(QuoteDiscountRule(rule_set_id=rs.id, org_id="seed-org",
                                      type=dtype, condition=cond, discount_bp=bp,
                                      stackable=stack, cap_bp=cap))
    session.commit()
    return {"rule_set_id": rs.id}
