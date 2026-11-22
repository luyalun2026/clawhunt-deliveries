# -*- coding: utf-8 -*-
"""金额计算引擎（价格规则表 + 只读派生金额）。

规则：金额一律以「分」为整数存储；请求体不得携带任何派生金额字段，
所有金额只能由本模块按规则表计算，保证「库内金额 == 引擎结果」。
"""

PRICE_RULES = {
    # 每种单元的挂牌月租金（分），虚构数据
    "base_monthly_cents": {"studio": 480_000, "office": 760_000, "suite": 1_280_000},
    "deposit_months": 3,          # 押金 = 3 个月
    "first_year_months": 12,      # 首年金额 = 12 个月
    "max_concession_bps": 1_500,  # 让价上限 15%
}

# 客户端不得写入的派生/只读金额字段（请求体出现即 422）
READONLY_AMOUNT_FIELDS = (
    "final_monthly_cents",
    "contract_total_cents",
    "first_year_amount_cents",
    "deposit_cents",
    "concession_bps",
    "amount_cents",
)


class RuleError(ValueError):
    """价格规则校验失败（映射为 422）。"""


def compute_amounts(unit_type, concession_bps=0, lease_months=12):
    base = PRICE_RULES["base_monthly_cents"].get(unit_type)
    if base is None:
        raise RuleError("unknown unit_type: %s" % unit_type)
    if not isinstance(concession_bps, int) or isinstance(concession_bps, bool):
        raise RuleError("concession_bps must be int")
    if concession_bps < 0 or concession_bps > PRICE_RULES["max_concession_bps"]:
        raise RuleError("concession_bps out of range")
    if lease_months < 1 or lease_months > 60:
        raise RuleError("lease_months out of range")

    final_monthly = base * (10_000 - concession_bps) // 10_000
    return {
        "unit_type": unit_type,
        "concession_bps": concession_bps,
        "lease_months": lease_months,
        "final_monthly_cents": final_monthly,
        "deposit_cents": final_monthly * PRICE_RULES["deposit_months"],
        "contract_total_cents": final_monthly * lease_months,
        "first_year_amount_cents": final_monthly * PRICE_RULES["first_year_months"],
    }
