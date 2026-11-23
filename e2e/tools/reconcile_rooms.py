# -*- coding: utf-8 -*-
"""房态 / 租约 / 合同台账三方一致性核对脚本（只读）。

用法：
    python e2e/tools/reconcile_rooms.py --fixtures tests/fixtures/consistent
    python e2e/tools/reconcile_rooms.py --base-url http://127.0.0.1:8000 --out diff.csv

退出码：0 无差异；2 有差异；3 取数失败。
差异 CSV 表头：type,room,contract,expected,actual
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from readonly_client import ReadOnlyClient  # noqa: E402

HEADER = ["type", "room", "contract", "expected", "actual"]
EPS_BP = 50          # 出租率容差 0.5pp（50 基点）


# ---------------------------------------------------------------- 规范化
def as_date(v: Any) -> date | None:
    if not v:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    s = str(v)[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _f(c: Any, key: str):
    """兼容 dict 与 dataclass 两种视图。"""
    if isinstance(c, dict):
        return c.get(key)
    return getattr(c, key, None)


def active(c: Any, as_of: date) -> bool:
    if _f(c, "status") != "active":
        return False
    end = as_date(_f(c, "end_date"))
    return end is None or end >= as_of


def expired(c: Any, as_of: date) -> bool:
    end = as_date(_f(c, "end_date"))
    return _f(c, "status") == "expired" or (end is not None and end < as_of)


@dataclass
class Room:
    room_id: str
    kind: str                 # office / workstation_zone
    status: str               # leased / vacant / maintenance
    tenant_id: str | None
    expire_date: date | None
    seat_total: int | None
    seat_leased: int | None
    deleted: bool


@dataclass
class Contract:
    contract_id: str
    status: str
    tenant_id: str
    space_id: str
    seats: int
    start_date: date | None
    end_date: date | None


def norm_rooms(raw: list[dict]) -> list[Room]:
    out = []
    for r in raw:
        out.append(Room(
            room_id=r.get("id") or r.get("room_id"),
            kind=r.get("kind") or "office",
            status=(r.get("status") or "").lower(),
            tenant_id=r.get("tenant_id"),
            expire_date=as_date(r.get("expire_date") or r.get("lease_end")),
            seat_total=r.get("seat_total"),
            seat_leased=r.get("seat_leased"),
            deleted=bool(r.get("deleted_at")),
        ))
    return out


def norm_contracts(raw: list[dict]) -> list[Contract]:
    return [Contract(
        contract_id=c.get("id") or c.get("contract_id"),
        status=(c.get("status") or "").lower(),
        tenant_id=c.get("tenant_id"),
        space_id=c.get("space_id") or c.get("room_id"),
        seats=int(c.get("seats") or 0),
        start_date=as_date(c.get("start_date")),
        end_date=as_date(c.get("end_date")),
    ) for c in raw]


# ---------------------------------------------------------------- 核对
def reconcile(rooms: list[Room], contracts: list[Contract], as_of: date,
              dash_rate_bp: int | None = None) -> list[dict]:
    live = [r for r in rooms if not r.deleted]
    by_space: dict[str, list[Contract]] = {}
    for c in contracts:
        by_space.setdefault(c.space_id, []).append(c)

    diffs: list[dict] = []

    def add(t, room, contract, exp, act):
        diffs.append({"type": t, "room": room, "contract": contract,
                      "expected": exp, "actual": act})

    for r in live:
        cs = by_space.get(r.room_id, [])
        act = [c for c in cs if active(c, as_of)]
        exp = [c for c in cs if expired(c, as_of)]

        if r.kind == "office" and len(act) > 1:
            # 独立办公室只能有一份生效合同；工位区允许多份（不同企业分租不同工位）
            add("duplicate_active_contract", r.room_id,
                ",".join(sorted(c.contract_id for c in act)), 1, len(act))

        if r.kind == "office":
            if r.status == "leased" and not act:
                add("leased_without_contract", r.room_id, "", "有效合同", "无")
            if act:
                c = act[0]
                if r.status != "leased":
                    add("contract_space_not_leased", r.room_id, c.contract_id, "leased", r.status)
                if r.tenant_id and c.tenant_id and r.tenant_id != c.tenant_id:
                    add("tenant_mismatch", r.room_id, c.contract_id, c.tenant_id, r.tenant_id)
                if r.expire_date and c.end_date and r.expire_date != c.end_date:
                    add("expire_date_mismatch", r.room_id, c.contract_id,
                        c.end_date.isoformat(), r.expire_date.isoformat())
            if r.status == "leased" and not act and exp:
                add("expired_contract_room_leased", r.room_id,
                    exp[0].contract_id, "vacant", "leased")

    # 工位区：已租工位数 = 该区所有生效合同 seats 之和
    for r in live:
        if r.kind != "workstation_zone":
            continue
        seats = sum(c.seats for c in contracts
                    if active(c, as_of) and c.space_id == r.room_id)
        if r.seat_leased is not None and seats != r.seat_leased:
            add("seat_sum_mismatch", r.room_id, "", seats, r.seat_leased)

    # 出租率重算（按工位）
    total_seats = sum(r.seat_total or 0 for r in live if r.seat_total)
    leased_seats = sum(r.seat_leased or 0 for r in live if r.kind == "workstation_zone")
    leased_seats += sum(r.seat_total or 0 for r in live
                        if r.kind == "office" and r.status == "leased")
    if total_seats > 0 and dash_rate_bp is not None:
        calc_bp = round(leased_seats * 10000 / total_seats)
        if abs(calc_bp - dash_rate_bp) > EPS_BP:
            add("occupancy_mismatch", "", "", dash_rate_bp, calc_bp)

    return diffs


# ---------------------------------------------------------------- 输出
def write_csv(diffs: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for d in diffs:
            w.writerow(d)


def run(client: ReadOnlyClient, as_of: date, out_csv: str) -> tuple[int, list[dict]]:
    rooms_raw = client.rooms()
    contracts_raw = client.contracts()
    rooms = norm_rooms(rooms_raw.get("items", rooms_raw) if isinstance(rooms_raw, dict) else rooms_raw)
    contracts = norm_contracts(
        contracts_raw.get("items", contracts_raw) if isinstance(contracts_raw, dict) else contracts_raw)

    dash_bp = None
    try:
        dash = client.dashboard(as_of.isoformat())
        dash_bp = int(dash.get("occupancy_rate_bp")) if dash.get("occupancy_rate_bp") is not None else None
    except Exception as e:                      # 驾驶舱不可用时降级
        print(f"[warn] 驾驶舱指标不可用，跳过出租率比对：{e}", file=sys.stderr)

    diffs = reconcile(rooms, contracts, as_of, dash_bp)
    write_csv(diffs, out_csv)
    print(f"rooms={len([r for r in rooms if not r.deleted])} contracts={len(contracts)} diffs={len(diffs)}")
    for d in diffs:
        print("  {type}: room={room} contract={contract} expected={expected} actual={actual}".format(**d))
    return (0 if not diffs else 2), diffs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="")
    ap.add_argument("--fixtures", default=None)
    ap.add_argument("--as-of", default=date.today().isoformat())
    ap.add_argument("--out", default="out/reconcile_diff.csv")
    a = ap.parse_args(argv)
    client = ReadOnlyClient(base_url=a.base_url, fixtures=a.fixtures)
    try:
        code, _ = run(client, as_date(a.as_of) or date.today(), a.out)
    except Exception as e:
        print(f"[error] 取数失败：{e}", file=sys.stderr)
        return 3
    assert set(client.calls) <= {"GET"}, client.calls
    return code


if __name__ == "__main__":
    raise SystemExit(main())
