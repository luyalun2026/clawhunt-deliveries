# -*- coding: utf-8 -*-
"""#2829 招商顾问线索越权用例（资源 × 操作参数化）。"""
import copy
import json
import os

import pytest

from app.authz import (A, ANON, B, ROLES, SITE_LEAD, SUP, Actor, Api, Lead, seed)

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATRIX = json.load(open(os.path.join(PKG, "matrix.json"), encoding="utf-8"))

UNAUTHORIZED_OPS = ["detail", "quote", "contract", "change_owner", "export_contains", "search"]


def call(api, actor, op, lead_id="L-B1", **kw):
    """统一的调用入口：把 6 类操作映射到 Api 方法。"""
    if op == "detail":
        return api.get_lead(actor, lead_id)
    if op == "quote":
        return api.get_quote(actor, lead_id)
    if op == "contract":
        return api.get_contract(actor, lead_id)
    if op == "change_owner":
        return api.change_owner(actor, lead_id, kw.get("new_owner", "consultant-a"))
    if op == "export":
        return api.export_leads(actor, kw.get("page", 1), kw.get("size", 100))
    if op == "search":
        return api.search(actor, kw.get("q", ""))
    if op == "list":
        return api.list_leads(actor)
    raise ValueError(op)


# ============================================================ AC1 列表恰好 8 条
def test_01_ac1_a_list_returns_exactly_eight():
    api = seed()
    code, body = api.list_leads(A)
    assert code == 200
    assert body["total"] == len(body["items"]) == 8     # 5 条本人 + 3 条公海
    ids = {r["id"] for r in body["items"]}
    assert len({i for i in ids if i.startswith("L-A")}) == 5
    assert len({i for i in ids if i.startswith("L-P")}) == 3
    assert not {i for i in ids if i.startswith("L-B")}


def test_02_ac1_list_never_contains_others_leads():
    api = seed()
    _, body = api.list_leads(A)
    names = [r["ent_name"] for r in body["items"]]
    assert not [n for n in names if "乙企业" in n]


def test_03_ac1_deleted_lead_absent_from_list():
    api = seed()
    _, body = api.list_leads(B)
    ids = {r["id"] for r in body["items"]}
    assert "L-DEL" not in ids
    assert body["total"] == 8                            # B 同样是 5 + 3


# ============================================================ AC2 六类越权全拒
@pytest.mark.parametrize("op", UNAUTHORIZED_OPS)
def test_04_ac2_six_unauthorized_ops_denied(op):
    api = seed()
    if op == "export_contains":
        code, body = api.export_leads(A)
        assert code == 200
        assert not [r for r in body["rows"] if r["id"].startswith("L-B")]
    elif op == "search":
        code, body = api.search(A, "乙企业")
        assert code == 200 and body["total"] == 0
    else:
        code, body = call(api, A, op)
        assert code in (403, 404)
        assert body["error"] in ("forbidden", "not_found")


def test_05_ac2_status_codes_by_semantics():
    api = seed()
    assert api.get_lead(A, "L-B1")[0] == 404
    assert api.get_quote(A, "L-B1")[0] == 404
    assert api.get_contract(A, "L-B1")[0] == 404
    assert api.change_owner(A, "L-B1", "consultant-a")[0] == 403


def test_06_ac2_denial_body_is_identical_for_missing_and_hidden():
    api = seed()
    hidden = api.get_lead(A, "L-B1")
    missing = api.get_lead(A, "L-NOT-EXIST")
    assert hidden == missing == (404, {"error": "not_found"})


def test_07_ac2_quote_and_contract_payload_never_leaks():
    api = seed()
    for fn in (api.get_quote, api.get_contract):
        code, body = fn(A, "L-B1")
        assert code == 404
        assert "quote_cent" not in body and "contract_id" not in body


def test_08_ac2_change_owner_does_not_mutate_state():
    api = seed()
    before = api.snapshot()
    api.change_owner(A, "L-B1", "consultant-a")
    assert api.snapshot() == before
    assert api.leads["L-B1"].owner_id == "consultant-b"


def test_09_ac2_pool_lead_cannot_be_taken_by_patching_owner():
    api = seed()
    code, body = api.change_owner(A, "L-P1", "consultant-a")
    assert code == 403 and body["code"] == "FORBIDDEN_NOT_OWNER"
    assert api.leads["L-P1"].owner_id is None


# ============================================================ AC3 导出行数 = 8
def test_10_ac3_export_rows_equal_list_rows():
    api = seed()
    _, lst = api.list_leads(A)
    code, exp = api.export_leads(A)
    assert code == 200 and exp["total"] == lst["total"] == 8
    assert {r["id"] for r in exp["rows"]} == {r["id"] for r in lst["items"]}


def test_11_ac3_export_whitelist_excludes_b_leads():
    api = seed()
    _, exp = api.export_leads(A)
    b_ids = {f"L-B{i}" for i in range(1, 6)}
    assert not (b_ids & {r["id"] for r in exp["rows"]})


def test_12_ac3_export_pagination_consistent():
    api = seed()
    _, p1 = api.export_leads(A, page=1, size=3)
    _, p2 = api.export_leads(A, page=2, size=3)
    _, p3 = api.export_leads(A, page=3, size=3)
    ids = [r["id"] for r in p1["rows"] + p2["rows"] + p3["rows"]]
    assert len(ids) == 8 and len(set(ids)) == 8
    assert p1["total"] == p2["total"] == p3["total"] == 8


# ============================================================ AC4 审计条数
def test_13_ac4_audit_count_equals_attempts():
    api = seed()
    attempts = 0
    for op in ("detail", "quote", "contract", "change_owner"):
        call(api, A, op)
        attempts += 1
    api.search(A, "乙企业")            # 不产生 denied（搜索是过滤而非拒绝）
    api.export_leads(A)                # 同上
    assert len(api.audit_denied()) == attempts == 4


def test_14_ac4_audit_records_actor_resource_path():
    api = seed()
    api.get_lead(A, "L-B1")
    a = api.audit_denied()[0]
    assert a["actor_id"] == "consultant-a"
    assert a["resource_type"] == "lead" and a["resource_id"] == "L-B1"
    assert a["path"] == "/api/leads/L-B1" and a["result"] == "denied"


def test_15_ac4_normal_access_produces_no_denied_audit():
    api = seed()
    api.get_lead(A, "L-A1")
    api.get_quote(A, "L-A1")
    api.get_contract(A, "L-A1")
    api.list_leads(A)
    assert api.audit_denied() == []


def test_16_ac4_audit_denied_count_matches_matrix_denials():
    """逐单元格用独立实例派发：每次拒绝都必须恰好落 1 条 access_denied。"""
    denied = 0
    for cell in MATRIX["cells"]:
        if cell["expect"] == "allow":
            continue
        api = seed()
        code, _ = call(api, ROLES[cell["role"]], cell["op"], cell["lead"])
        assert code in (403, 404), cell
        assert len(api.audit_denied()) == 1, cell
        denied += 1
    assert denied == MATRIX["summary"]["deny_or_not_found"] == 42


def test_24_ac4_matrix_allow_cells_are_allowed():
    for cell in MATRIX["cells"]:
        if cell["expect"] != "allow":
            continue
        api = seed()          # 独立实例：避免改 owner 的用例污染后续单元格
        code, _ = call(api, ROLES[cell["role"]], cell["op"], cell["lead"])
        assert code == 200, cell
        assert api.audit_denied() == [], cell


# ============================================================ 边界组
def test_17_edge_supervisor_sees_thirteen():
    api = seed()
    code, body = api.list_leads(SUP)
    assert code == 200
    assert body["total"] == 13          # 5 + 5 + 3（软删除与本团队外线索不计）
    assert not [r for r in body["items"] if r["id"] == "L-DEL"]


def test_18_edge_site_lead_scoped_to_site():
    api = seed()
    _, body = api.list_leads(SITE_LEAD)
    ids = {r["id"] for r in body["items"]}
    assert "L-OTHER-SITE" not in ids
    assert body["total"] == 13


def test_19_edge_url_variants_still_denied():
    api = seed()
    for path in ("/api/leads/L-B1/", "/API/Leads/L-B1", "/api/leads/../leads/L-B1",
                 "/api/leads/L-B1?x=1"):
        code, body = api.get_lead(A, "L-B1", path=path)
        assert code == 404, path


def test_20_edge_unauthenticated_gets_401_and_audit():
    api = seed()
    code, body = api.list_leads(ANON)
    assert code == 401
    assert len(api.audit_denied()) == 1


def test_21_edge_b_cannot_read_a_leads():
    api = seed()
    assert api.get_lead(B, "L-A1")[0] == 404
    assert api.get_quote(B, "L-A1")[0] == 404
    assert api.change_owner(B, "L-A1", "consultant-b")[0] == 403


def test_22_edge_deleted_lead_invisible_everywhere():
    api = seed()
    code, _ = api.get_lead(B, "L-DEL")
    assert code == 404
    _, exp = api.export_leads(B)
    assert "L-DEL" not in {r["id"] for r in exp["rows"]}
    assert api.search(B, "已删企业")[1]["total"] == 0


def test_23_edge_matrix_file_covers_all_resources_and_ops():
    assert set(MATRIX["ops"]) == {"list", "detail", "quote", "contract", "change_owner",
                                  "export", "search"}
    assert len(MATRIX["cells"]) >= 40
    assert all(c["expect"] in ("allow", "deny", "not_found") for c in MATRIX["cells"])
