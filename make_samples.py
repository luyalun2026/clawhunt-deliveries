#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 10 份样例合同与期望分期。

★ 期望值由 reference.py（独立参照算法，整数运算）给出，**不由 build_plan 自证**；
  生成后再用 build_plan 跑一遍做交叉比对，两边不一致就退出码 1。
★ 样例事件按本单范围给出的 payload 形态：fees 只带 period_amount_cents，不带 total_cents。
"""
import json
import os
import sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import schedule as sch  # noqa: E402
import reference as ref  # noqa: E402

SAMPLES = [
    # (名称, 起, 止, 周期, 租金周期金额, 会籍周期金额, 押金, 提前天数)
    ("12m_quarter_tail",   "2026-01-01", "2026-12-31", "quarter",   300000,  90000, 50000, 10),
    ("12m_month_exact",    "2026-01-01", "2026-12-31", "month",     100000,   None, 20000,  5),
    ("10m_quarter_tail",   "2026-01-01", "2026-10-31", "quarter",   300000,   None,     0, 10),
    ("24m_year_multi",     "2026-01-01", "2027-12-31", "year",     1200000, 300000, 100000, 15),
    ("6m_half_year",       "2026-01-01", "2026-06-30", "half_year", 500000,   None, 30000,  0),
    ("8m_month_tail",      "2026-03-15", "2026-11-14", "month",      80000,  20000, 15000,  7),
    ("36m_quarter_multi",  "2026-01-01", "2028-12-31", "quarter",   250000,   None, 80000, 20),
    ("1m_month_min",       "2026-05-01", "2026-05-31", "month",     100000,   None,     0,  0),
    ("18m_half_year_tail", "2026-01-01", "2027-08-15", "half_year", 450000,   None, 50000, 12),
    ("20m_month_tail",     "2026-02-01", "2027-10-15", "month",     120000,  30000, 60000,  3),
]


def build(name, s, e, cycle, rp, mp, dep, adv):
    fees = [{"fee_type": "rent", "period_amount_cents": rp}]
    if mp is not None:
        fees.append({"fee_type": "membership", "period_amount_cents": mp})
    return {"source_event_id": "evt-%s" % name, "contract_id": "HT-%s" % name,
            "company_id": "co-demo", "start_date": s, "end_date": e,
            "pay_cycle": cycle, "fees": fees, "deposit_cents": dep,
            "first_payment_date": s, "advance_days": adv}


def expected_from_reference(ev):
    """用参照算法算期望分期；到期日按同一规则独立算一遍。"""
    start = date.fromisoformat(ev["start_date"])
    end = date.fromisoformat(ev["end_date"])
    fpd = date.fromisoformat(ev["first_payment_date"])
    adv = int(ev["advance_days"])
    rows = []
    for fee in ev["fees"]:
        for seq, (kind, amt, ps, pe) in enumerate(
                ref.expected_rows(fee["period_amount_cents"], ev["pay_cycle"], start, end), 1):
            due = fpd if seq == 1 else ps - timedelta(days=adv)
            rows.append({"fee_type": fee["fee_type"], "seq": seq, "amount_cents": amt,
                         "due_date": due.isoformat(), "period": "%s~%s" % (ps, pe),
                         "kind": kind})
    if int(ev["deposit_cents"] or 0) > 0:
        rows.append({"fee_type": "deposit", "seq": 1,
                     "amount_cents": int(ev["deposit_cents"]),
                     "due_date": fpd.isoformat(), "period": "%s~%s" % (start, start),
                     "kind": "deposit"})
    per_type, counts = {}, {}
    for r in rows:
        per_type[r["fee_type"]] = per_type.get(r["fee_type"], 0) + r["amount_cents"]
        counts[r["fee_type"]] = counts.get(r["fee_type"], 0) + 1
    first_year_end = ref._shift(start, 12)
    first_year = sum(r["amount_cents"] for r in rows
                     if r["fee_type"] != "deposit"
                     and date.fromisoformat(r["period"].split("~")[0]) < first_year_end)
    return {"contract_id": ev["contract_id"], "pay_cycle": ev["pay_cycle"],
            "per_type_sum": per_type, "deposit_cents": ev["deposit_cents"],
            "installment_count": len(rows), "counts_by_type": counts,
            "first_year_amount_cents": first_year,
            "expected_by": "reference.py（独立参照算法，整数 divmod）",
            "installments": rows}


def main():
    outdir = os.path.join(HERE, "sample_contracts")
    os.makedirs(outdir, exist_ok=True)
    lines, all_ok = [], True
    for idx, args in enumerate(SAMPLES, 1):
        name = args[0]
        ev = build(name, *args[1:])
        expected = expected_from_reference(ev)
        plan = sch.build_plan(ev)
        actual = [{"fee_type": i.fee_type, "seq": i.seq, "amount_cents": i.amount_cents,
                   "due_date": i.due_date.isoformat(),
                   "period": "%s~%s" % (i.period_start, i.period_end), "kind": i.kind}
                  for i in plan.installments]
        match = (actual == expected["installments"]
                 and plan.first_year_amount_cents == expected["first_year_amount_cents"])
        all_ok = all_ok and match
        with open(os.path.join(outdir, "%02d_%s.json" % (idx, name)), "w",
                  encoding="utf-8") as f:
            json.dump(ev, f, ensure_ascii=False, indent=1)
        with open(os.path.join(outdir, "%02d_%s.expected.json" % (idx, name)), "w",
                  encoding="utf-8") as f:
            json.dump(expected, f, ensure_ascii=False, indent=1)
        tails = ",".join(str(r["amount_cents"]) for r in expected["installments"]
                         if r["kind"] == "tail") or "无"
        lines.append("%02d %-20s cycle=%-9s 分期=%2d 租金Σ=%8d 尾期=%s 双算法一致=%s"
                     % (idx, name, ev["pay_cycle"], expected["installment_count"],
                        expected["per_type_sum"]["rent"], tails, match))
    print("\n".join(lines))
    print("\n10 份样例：实现与参照算法逐字段一致 = %s" % all_ok)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
