# -*- coding: utf-8 -*-
"""生成资源 × 操作矩阵（规格声明，不调用被测系统；用例反过来校验实现）。"""
import json
import os

PKG = os.path.dirname(os.path.abspath(__file__))
ROLES = ["A", "B", "supervisor", "site_lead"]
LEADS = {
    "L-A1": "own_or_team",       # A 本人；supervisor 团队内；site_lead 本站
    "L-B1": "other",             # B 本人（对 A 是他人）
    "L-P1": "pool",              # 公海
    "L-DEL": "deleted",
    "L-NOT-EXIST": "missing",
}
OPS = ["detail", "quote", "contract", "change_owner"]


def expect(role: str, lead_id: str, kind: str, op: str) -> str:
    if kind == "missing":
        return "not_found"
    if kind == "deleted":
        return "not_found"
    if role in ("supervisor", "site_lead"):
        return "allow"
    # 顾问：本人才可操作自己的线索
    own = "L-A1" if role == "A" else "L-B1"
    if lead_id == own:
        return "allow"
    if kind == "pool":
        return "deny" if op == "change_owner" else "allow"
    # other 的线索
    return "deny" if op == "change_owner" else "not_found"


cells = []
for role in ROLES:
    for lead_id, kind in LEADS.items():
        for op in OPS:
            cells.append({"role": role, "lead": lead_id, "kind": kind, "op": op,
                          "expect": expect(role, lead_id, kind, op)})

matrix = {
    "generated_by": "_gen_matrix.py（声明式规则，不调用被测系统）",
    "ops": ["list", "detail", "quote", "contract", "change_owner", "export", "search"],
    "roles": ["A", "B", "supervisor", "site_lead", "anonymous"],
    "resources": list(LEADS),
    "cells": cells,
    "list_expectations": {
        "A": {"total": 8, "note": "5 条本人 + 3 条公海；不含 B、不含软删除、不含他站"},
        "B": {"total": 8, "note": "同上"},
        "supervisor": {"total": 13, "note": "团队 10 条 + 公海 3 条"},
        "site_lead": {"total": 13, "note": "本站 13 条（含 B 的 5 条），不含他站"},
        "anonymous": {"status": 401}
    },
    "export_expectations": {"A": {"rows": 8, "exclude_prefixes": ["L-B", "L-DEL", "L-OTHER"]},
                            "B": {"rows": 8, "exclude_prefixes": ["L-A", "L-DEL", "L-OTHER"]}},
    "search_expectations": {"A": {"q": "乙企业", "total": 0},
                            "B": {"q": "甲企业", "total": 0}},
    "summary": {
        "cells_total": len(cells),
        "deny_or_not_found": sum(1 for c in cells if c["expect"] != "allow"),
        "allow": sum(1 for c in cells if c["expect"] == "allow"),
    },
}

with open(os.path.join(PKG, "matrix.json"), "w", encoding="utf-8") as f:
    json.dump(matrix, f, ensure_ascii=False, indent=1)
print("cells", len(cells), matrix["summary"])
