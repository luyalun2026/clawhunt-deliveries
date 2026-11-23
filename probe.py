# -*- coding: utf-8 -*-
"""实测采集：按 matrix.json 全量派发 → 输出单元格矩阵与审计对拍数字。"""
import json
import os

from app.authz import A, ANON, B, ROLES, SITE_LEAD, SUP, seed

PKG = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(PKG, "outputs")
os.makedirs(OUT, exist_ok=True)
MATRIX = json.load(open(os.path.join(PKG, "matrix.json"), encoding="utf-8"))


def dispatch(api, actor, op, lead):
    if op == "detail":
        return api.get_lead(actor, lead)
    if op == "quote":
        return api.get_quote(actor, lead)
    if op == "contract":
        return api.get_contract(actor, lead)
    if op == "change_owner":
        return api.change_owner(actor, lead, "consultant-a")
    raise ValueError(op)


rows = []
mismatch = 0
audit_total = 0
for cell in MATRIX["cells"]:
    api = seed()                      # 每格独立实例，避免改 owner 污染后续测量
    code, _ = dispatch(api, ROLES[cell["role"]], cell["op"], cell["lead"])
    ok = (code == 200) if cell["expect"] == "allow" else (code in (403, 404))
    mismatch += 0 if ok else 1
    audit_total += len(api.audit_denied())
    rows.append({**cell, "status": code, "ok": ok})

api = seed()                          # 独立实例做列表/导出/检索口径测量
lines = ["| 角色 | 线索 | 资源类型 | 操作 | 期望 | 实际状态码 | 结论 |", "|---|---|---|---|---|---|---|"]
for r in rows:
    lines.append(f"| {r['role']} | {r['lead']} | {r['kind']} | {r['op']} | {r['expect']} | "
                 f"{r['status']} | {'一致' if r['ok'] else '**不一致**'} |")
open(os.path.join(OUT, "matrix-cells.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

list_actual = {}
for name, actor in (("A", A), ("B", B), ("supervisor", SUP), ("site_lead", SITE_LEAD)):
    code, body = api.list_leads(actor)
    list_actual[name] = {"status": code, "total": body.get("total")}

exp_a = api.export_leads(A)[1]
exp_b = api.export_leads(B)[1]
search_a = api.search(A, "乙企业")[1]["total"]
search_b = api.search(B, "甲企业")[1]["total"]

summary = {
    "cells_total": len(rows),
    "cells_consistent": len(rows) - mismatch,
    "cells_mismatch": mismatch,
    "denials_expected": MATRIX["summary"]["deny_or_not_found"],
    "audit_denied_records": audit_total,
    "list_totals": list_actual,
    "export_rows": {"A": exp_a["total"], "B": exp_b["total"]},
    "export_leaks": {"A_has_B": any(r["id"].startswith("L-B") for r in exp_a["rows"]),
                     "B_has_A": any(r["id"].startswith("L-A") for r in exp_b["rows"])},
    "search_cross_tenant_hits": {"A_searches_B": search_a, "B_searches_A": search_b},
}
json.dump(summary, open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False))
