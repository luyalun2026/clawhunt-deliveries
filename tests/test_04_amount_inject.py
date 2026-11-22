# -*- coding: utf-8 -*-
"""④ 金额只读：对全部写接口注入 6 个派生金额字段一律 422；
每次注入后逐一断言库内金额仍等于计算引擎结果、对象数量不变（未被篡改）；
合法业务体夹带金额字段、嵌套位置（创建体 / 电子签回调 payload）注入金额，
要么被整体拒绝、要么被忽略，库内金额均不变。"""
import pytest

from app.main import create_app
from app.money import READONLY_AMOUNT_FIELDS, compute_amounts
from tests.helpers import H, fill_path, obj_id, user, write_routes

WRITE_ROUTES = write_routes(create_app())
OWNER = user("a", 1, "c1")

AMOUNT_KEYS = ("final_monthly_cents", "deposit_cents",
               "contract_total_cents", "first_year_amount_cents")
COUNTED = ("leads", "followups", "visits", "quotes", "contracts",
           "attachments", "esign_events")


def assert_amounts_match_engine(db):
    """库内金额一致性（每次注入后调用）：
    报价 4 个金额字段 + concession_bps == compute_amounts()；
    合同 contract_total_cents == 其关联报价的引擎结果。"""
    for q in db["quotes"].values():
        expect = compute_amounts(q["unit_type"], q["concession_bps"], q["lease_months"])
        assert q["concession_bps"] == expect["concession_bps"], (q["id"], "concession_bps")
        for key in AMOUNT_KEYS:
            assert q[key] == expect[key], (q["id"], key, q[key], expect[key])
    for c in db["contracts"].values():
        q = db["quotes"][c["quote_id"]]
        expect = compute_amounts(q["unit_type"], q["concession_bps"], q["lease_months"])
        assert c["contract_total_cents"] == expect["contract_total_cents"], \
            (c["id"], c["contract_total_cents"], expect["contract_total_cents"])


def _counts(db):
    return {name: len(db[name]) for name in COUNTED}


@pytest.mark.parametrize("field", READONLY_AMOUNT_FIELDS)
@pytest.mark.parametrize("method,path", WRITE_ROUTES,
                         ids=["%s %s" % r for r in WRITE_ROUTES])
def test_write_endpoints_reject_readonly_amount_fields(client, db, method, path, field):
    url = fill_path(path, OWNER)
    counts_before = _counts(db)
    resp = client.request(method, url, json={field: 123456}, headers=H(OWNER))
    assert resp.status_code == 422, (method, url, field, resp.status_code, resp.text)
    detail = resp.json()["detail"]
    assert detail["code"] == "READONLY_FIELD"
    assert field in detail["fields"]
    # 每次注入后：对象数量不变，库内金额仍与引擎一致（逐字段核对，不只看报价一处）
    assert _counts(db) == counts_before, (method, url, field)
    assert_amounts_match_engine(db)


def test_write_route_count_matches_openapi():
    # 18 条写接口（6 类对象 × 各自写方法 + 2 个动作 + 电子签回调），数量变化时必须显式复核
    assert len(WRITE_ROUTES) == 19, [r for r in WRITE_ROUTES]


def test_quote_amounts_come_from_engine(client, db):
    lead_id = obj_id("lead", OWNER)
    created = client.post("/api/sales/quotes",
                          json={"lead_id": lead_id, "unit_type": "office",
                                "lease_months": 24, "requested_concession_bps": 500},
                          headers=H(OWNER))
    assert created.status_code == 200, created.text
    quote = created.json()
    expect = compute_amounts("office", 500, 24)
    for key in AMOUNT_KEYS + ("concession_bps",):
        assert quote[key] == expect[key], key
    assert db["quotes"][quote["id"]]["contract_total_cents"] == expect["contract_total_cents"]

    # 注入被拒后，库内金额必须仍与引擎一致（全部 4 个金额字段逐项复核，未被篡改）
    for field in READONLY_AMOUNT_FIELDS:
        bad = client.put("/api/sales/quotes/%s" % quote["id"], json={field: 1},
                         headers=H(OWNER))
        assert bad.status_code == 422
    stored = db["quotes"][quote["id"]]
    for key in AMOUNT_KEYS:
        assert stored[key] == expect[key], key
    assert_amounts_match_engine(db)


def test_out_of_range_concession_is_422(client):
    resp = client.post("/api/sales/quotes",
                       json={"lead_id": obj_id("lead", OWNER), "unit_type": "office",
                             "lease_months": 12, "requested_concession_bps": 9999},
                       headers=H(OWNER))
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "RULE_ERROR"


# ---------------------------------------------------- 夹带 / 嵌套位置注入
def test_legit_body_with_smuggled_amount_field_is_422(client, db):
    """合法业务请求体夹带金额字段 → 整体 422，合法字段也不生效，库内金额不变。"""
    quote_id = obj_id("quote", OWNER)
    stored = db["quotes"][quote_id]
    assert stored["lease_months"] == 24
    resp = client.put("/api/sales/quotes/%s" % quote_id,
                      json={"lease_months": 36, "final_monthly_cents": 123456},
                      headers=H(OWNER))
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["code"] == "READONLY_FIELD"
    assert db["quotes"][quote_id]["lease_months"] == 24
    assert_amounts_match_engine(db)


def test_nested_amount_in_create_body_is_ignored(client, db):
    """创建类接口在嵌套位置注入金额 → 请求成功，但金额一律由引擎计算，
    嵌套内容不落库，库内 == 引擎。"""
    resp = client.post("/api/sales/quotes",
                       json={"lead_id": obj_id("lead", OWNER), "unit_type": "suite",
                             "lease_months": 12, "requested_concession_bps": 300,
                             "meta": {"contract_total_cents": 999999999}},
                       headers=H(OWNER))
    assert resp.status_code == 200, resp.text
    expect = compute_amounts("suite", 300, 12)
    stored = db["quotes"][resp.json()["id"]]
    for key in AMOUNT_KEYS:
        assert stored[key] == expect[key], key
    assert "meta" not in stored
    assert_amounts_match_engine(db)


def test_nested_amount_in_esign_payload_is_ignored(client, db):
    """电子签回调 payload 嵌套金额注入：签名合法 → 回调受理，
    嵌套金额被忽略，合同金额仍等于关联报价的引擎结果。"""
    from app.security import sign_payload
    from tests.conftest import ESIGN_SECRET
    contract_id = obj_id("contract", OWNER)
    payload = {"contract_id": contract_id, "signed_at": "2026-12-02T09:00:00+08:00",
               "esign_ref": "ES-FICT-0002", "contract_total_cents": 999999999,
               "final_monthly_cents": 999999999}
    body = {"payload": payload, "signature": sign_payload(ESIGN_SECRET, payload)}
    resp = client.post("/api/sales/esign/callback", json=body)
    assert resp.status_code == 200, resp.text
    contract = db["contracts"][contract_id]
    assert contract["status"] == "signed"
    q = db["quotes"][contract["quote_id"]]
    expect = compute_amounts(q["unit_type"], q["concession_bps"], q["lease_months"])
    assert contract["contract_total_cents"] == expect["contract_total_cents"]
    assert contract["contract_total_cents"] != 999999999
    assert_amounts_match_engine(db)
