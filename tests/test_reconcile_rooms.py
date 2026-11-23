# -*- coding: utf-8 -*-
"""#2837 用例：AC1 四类差异全检出 / AC2 一致时 exit 0 且 CSV 仅表头 /
AC3 只发 GET / AC4 出租率重算与驾驶舱对拍，外加边界 5 例。
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
from datetime import date

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "e2e", "tools"))

import reconcile_rooms as rr          # noqa: E402
from readonly_client import ReadOnlyClient, ReadOnlyViolation  # noqa: E402

AS_OF = date(2026, 11, 23)
FIX = os.path.join(ROOT, "tests", "fixtures")


@pytest.fixture(scope="session", autouse=True)
def _build():
    """夹具缺失时现场生成，保证可离线复跑。"""
    if not os.path.isdir(os.path.join(FIX, "consistent")):
        import subprocess
        subprocess.run([sys.executable, os.path.join(ROOT, "tests", "make_fixtures.py")], check=True)


def ec(fixtures: str):
    return ReadOnlyClient(fixtures=os.path.join(FIX, fixtures))


def read_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------------ AC1
def test_ac1_four_kinds_detected(tmp_path):
    out = str(tmp_path / "diff.csv")
    code, diffs = rr.run(ec("inconsistent"), AS_OF, out)
    kinds = {}
    for d in diffs:
        kinds[d["type"]] = kinds.get(d["type"], 0) + 1
    assert code == 2
    for k in ("leased_without_contract", "contract_space_not_leased",
              "expired_contract_room_leased", "seat_sum_mismatch"):
        assert kinds.get(k) == 1, (k, kinds)
    rows = read_csv(out)
    assert len(rows) == len(diffs)
    assert set(rows[0]) == {"type", "room", "contract", "expected", "actual"}


def test_ac1_csv_row_per_kind(tmp_path):
    out = str(tmp_path / "diff.csv")
    rr.run(ec("inconsistent"), AS_OF, out)
    rows = read_csv(out)
    by = {}
    for r in rows:
        by.setdefault(r["type"], []).append(r)
    assert by["leased_without_contract"][0]["room"] == "R-201"
    assert by["contract_space_not_leased"][0]["room"] == "R-202"
    assert by["expired_contract_room_leased"][0]["room"] == "R-201"
    assert by["seat_sum_mismatch"][0]["expected"] == "112"
    assert by["seat_sum_mismatch"][0]["actual"] == "118"


# ------------------------------------------------------------------ AC2
def test_ac2_consistent_exit_zero_header_only(tmp_path):
    out = str(tmp_path / "ok.csv")
    code, diffs = rr.run(ec("consistent"), AS_OF, out)
    assert code == 0 and diffs == []
    raw = open(out, encoding="utf-8-sig").read().strip().splitlines()
    assert len(raw) == 1 and raw[0] == "type,room,contract,expected,actual"


# ------------------------------------------------------------------ AC3
def test_ac3_only_get_calls(tmp_path):
    c = ec("inconsistent")
    rr.run(c, AS_OF, str(tmp_path / "d.csv"))
    assert set(c.calls) == {"GET"}
    assert len(c.calls) == 3            # rooms + contracts + dashboard


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_ac3_write_methods_raise(method):
    c = ec("consistent")
    with pytest.raises(ReadOnlyViolation):
        getattr(c, method)("/api/x", {})


def test_ac3_no_write_in_source():
    src = open(os.path.join(ROOT, "e2e", "tools", "reconcile_rooms.py"), encoding="utf-8").read()
    for kw in ("INSERT", "UPDATE ", "DELETE FROM"):
        assert kw not in src


# ------------------------------------------------------------------ AC4 出租率
def test_ac4_occupancy_match_no_row(tmp_path):
    _, diffs = rr.run(ec("consistent"), AS_OF, str(tmp_path / "d.csv"))
    assert not any(d["type"] == "occupancy_mismatch" for d in diffs)


def test_ac4_occupancy_deviation_detected(tmp_path):
    _, diffs = rr.run(ec("inconsistent"), AS_OF, str(tmp_path / "d.csv"))
    occ = [d for d in diffs if d["type"] == "occupancy_mismatch"]
    assert len(occ) == 1
    assert str(occ[0]["expected"]) == "6500"
    # 重算 = (3 间已租 office ×10 + 工位区 118) / (4 间 office ×10 + 工位区 120) = 148/160 = 9250 bp
    assert str(occ[0]["actual"]) == "9250"


# ------------------------------------------------------------------ 边界 5 例
def test_edge_empty_dataset(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    (d / "api_space_rooms.json").write_text('{"items": []}', encoding="utf-8")
    (d / "api_contracts.json").write_text('{"items": []}', encoding="utf-8")
    (d / "api_dashboard_metrics.json").write_text('{"occupancy_rate_bp": null}', encoding="utf-8")
    code, diffs = rr.run(ReadOnlyClient(fixtures=str(d)), AS_OF, str(tmp_path / "e.csv"))
    assert code == 0 and diffs == []


def test_edge_soft_deleted_room_skipped(tmp_path):
    d = tmp_path / "del"
    d.mkdir()
    rooms = {"items": [{"id": "R-X", "kind": "office", "status": "leased",
                        "tenant_id": "T-1", "expire_date": None, "seat_total": 10,
                        "seat_leased": None, "deleted_at": "2026-11-01"}]}
    (d / "api_space_rooms.json").write_text(json.dumps(rooms), encoding="utf-8")
    (d / "api_contracts.json").write_text('{"items": []}', encoding="utf-8")
    (d / "api_dashboard_metrics.json").write_text('{"occupancy_rate_bp": null}', encoding="utf-8")
    _, diffs = rr.run(ReadOnlyClient(fixtures=str(d)), AS_OF, str(tmp_path / "d.csv"))
    assert diffs == []


def test_edge_duplicate_active_contract(tmp_path):
    d = tmp_path / "dup"
    d.mkdir()
    rooms = {"items": [{"id": "R-1", "kind": "office", "status": "leased", "tenant_id": "T",
                        "expire_date": "2027-01-01", "seat_total": 10, "seat_leased": None,
                        "deleted_at": None}]}
    cts = {"items": [
        {"id": "C-A", "status": "active", "tenant_id": "T", "space_id": "R-1", "seats": 10,
         "start_date": "2026-01-01", "end_date": "2027-01-01"},
        {"id": "C-B", "status": "active", "tenant_id": "T", "space_id": "R-1", "seats": 10,
         "start_date": "2026-02-01", "end_date": "2027-01-01"}]}
    (d / "api_space_rooms.json").write_text(json.dumps(rooms), encoding="utf-8")
    (d / "api_contracts.json").write_text(json.dumps(cts), encoding="utf-8")
    (d / "api_dashboard_metrics.json").write_text('{"occupancy_rate_bp": null}', encoding="utf-8")
    _, diffs = rr.run(ReadOnlyClient(fixtures=str(d)), AS_OF, str(tmp_path / "d.csv"))
    assert [x["type"] for x in diffs].count("duplicate_active_contract") == 1


def test_edge_expire_date_one_day_diff(tmp_path):
    """到期日相差 1 天必须检出（日期比较，不因时分秒误判）。"""
    d = tmp_path / "day"
    d.mkdir()
    rooms = {"items": [{"id": "R-1", "kind": "office", "status": "leased", "tenant_id": "T",
                        "expire_date": "2027-06-30", "seat_total": 10, "seat_leased": None,
                        "deleted_at": None}]}
    cts = {"items": [{"id": "C-A", "status": "active", "tenant_id": "T", "space_id": "R-1",
                      "seats": 10, "start_date": "2026-01-01", "end_date": "2027-07-01"}]}
    (d / "api_space_rooms.json").write_text(json.dumps(rooms), encoding="utf-8")
    (d / "api_contracts.json").write_text(json.dumps(cts), encoding="utf-8")
    (d / "api_dashboard_metrics.json").write_text('{"occupancy_rate_bp": null}', encoding="utf-8")
    _, diffs = rr.run(ReadOnlyClient(fixtures=str(d)), AS_OF, str(tmp_path / "d.csv"))
    assert [x["type"] for x in diffs] == ["expire_date_mismatch"]


def test_edge_dashboard_missing_degrades(tmp_path, capsys):
    """驾驶舱接口缺失时降级为告警，其余核对照常，不崩溃。"""
    d = tmp_path / "nodash"
    d.mkdir()
    (d / "api_space_rooms.json").write_text(
        json.dumps({"items": [{"id": "R-1", "kind": "office", "status": "leased",
                               "tenant_id": "T", "expire_date": None, "seat_total": 10,
                               "seat_leased": None, "deleted_at": None}]}), encoding="utf-8")
    (d / "api_contracts.json").write_text('{"items": []}', encoding="utf-8")
    code, diffs = rr.run(ReadOnlyClient(fixtures=str(d)), AS_OF, str(tmp_path / "d.csv"))
    assert code == 2                                  # 仍检出 leased_without_contract
    assert [x["type"] for x in diffs] == ["leased_without_contract"]
    assert "驾驶舱" in capsys.readouterr().err


def test_edge_cli_exit_codes(tmp_path):
    assert rr.main(["--fixtures", os.path.join(FIX, "consistent"),
                    "--as-of", "2026-11-23", "--out", str(tmp_path / "a.csv")]) == 0
    assert rr.main(["--fixtures", os.path.join(FIX, "inconsistent"),
                    "--as-of", "2026-11-23", "--out", str(tmp_path / "b.csv")]) == 2
    assert rr.main(["--fixtures", str(tmp_path / "nope"),
                    "--as-of", "2026-11-23", "--out", str(tmp_path / "c.csv")]) == 3
