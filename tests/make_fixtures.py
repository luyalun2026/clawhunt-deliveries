# -*- coding: utf-8 -*-
"""生成 #2837 夹具：consistent（全一致）与 inconsistent（4 类差异各 1 条 + 出租率偏差）。

数据全部虚构。用法：python tests/make_fixtures.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
AS_OF = "2026-11-23"


def office(rid, status, tenant=None, expire=None, seats=10):
    return {"id": rid, "kind": "office", "status": status, "tenant_id": tenant,
            "expire_date": expire, "seat_total": seats, "seat_leased": None,
            "deleted_at": None}


def zone(rid, total, leased):
    return {"id": rid, "kind": "workstation_zone", "status": "leased", "tenant_id": None,
            "expire_date": None, "seat_total": total, "seat_leased": leased,
            "deleted_at": None}


def contract(cid, space, tenant, seats, end, status="active"):
    return {"id": cid, "status": status, "tenant_id": tenant, "space_id": space,
            "seats": seats, "start_date": "2026-01-01", "end_date": end}


def dump(dirname, rooms, contracts, dash_bp):
    d = os.path.join(HERE, "fixtures", dirname)
    os.makedirs(d, exist_ok=True)
    json.dump({"items": rooms}, open(os.path.join(d, "api_space_rooms.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump({"items": contracts}, open(os.path.join(d, "api_contracts.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump({"occupancy_rate_bp": dash_bp, "as_of": AS_OF},
              open(os.path.join(d, "api_dashboard_metrics.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"{dirname}: rooms={len(rooms)} contracts={len(contracts)} dash_bp={dash_bp}")


# ---------------- consistent ----------------
rooms = [
    office("R-101", "leased", "T-1", "2027-06-30"),
    office("R-102", "leased", "T-2", "2027-03-31"),
    office("R-103", "vacant"),
    zone("Z-01", 120, 100),
]
contracts = [
    contract("C-101", "R-101", "T-1", 10, "2027-06-30"),
    contract("C-102", "R-102", "T-2", 10, "2027-03-31"),
    contract("C-Z01", "Z-01", "T-3", 100, "2027-12-31"),
]
# 总工位 3*10 + 120 = 150；已租 10+10+100 = 120 → 8000 bp
dump("consistent", rooms, contracts, 8000)

# ---------------- inconsistent（4 类各 1 + 出租率偏差） ----------------
rooms2 = [
    office("R-101", "leased", "T-1", "2027-06-30"),          # 正常
    office("R-201", "leased", "T-9", "2027-01-31"),          # A 已租无生效合同（合同已到期）
    office("R-202", "vacant"),                                # B 生效合同但房态 vacant
    office("R-203", "leased", "T-4", "2027-05-31"),          # C 有生效合同，正常
    zone("Z-01", 120, 118),                                   # D 已租 118 ≠ 合同合计 112
]
contracts2 = [
    contract("C-101", "R-101", "T-1", 10, "2027-06-30"),
    contract("C-OLD", "R-201", "T-9", 10, "2026-10-31", status="expired"),
    contract("C-202", "R-202", "T-8", 10, "2027-09-30"),
    contract("C-203", "R-203", "T-4", 10, "2027-05-31"),
    contract("C-Z01A", "Z-01", "T-5", 60, "2027-12-31"),
    contract("C-Z01B", "Z-01", "T-6", 52, "2027-12-31"),
]
# 重算：office leased 3 间 × 10 = 30，工位区 118 → 148 / 150 = 9867 bp
# 驾驶舱给 6500 bp（偏差 33.7pp，必被检出）
dump("inconsistent", rooms2, contracts2, 6500)
