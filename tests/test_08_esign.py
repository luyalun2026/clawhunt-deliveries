# -*- coding: utf-8 -*-
"""⑧ 电子签回调：伪造签名拒绝；密钥只从环境变量读取（缺失即 500）。"""
from app.security import sign_payload
from tests.conftest import ESIGN_SECRET
from tests.helpers import H, obj_id, user

OWNER = user("a", 1, "c1")


def _payload(contract_id=None):
    return {"contract_id": contract_id or obj_id("contract", OWNER),
            "signed_at": "2026-12-02T09:00:00+08:00", "esign_ref": "ES-FICT-0001"}


def test_forged_signature_rejected(client):
    body = {"payload": _payload(), "signature": "0" * 64}
    resp = client.post("/api/sales/esign/callback", json=body)
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "ESIGN_INVALID_SIGNATURE"


def test_valid_signature_marks_contract_signed(client, db):
    payload = _payload()
    body = {"payload": payload, "signature": sign_payload(ESIGN_SECRET, payload)}
    resp = client.post("/api/sales/esign/callback", json=body)
    assert resp.status_code == 200, resp.text
    contract = db["contracts"][payload["contract_id"]]
    assert contract["status"] == "signed"
    assert contract["esign_ref"] == "ES-FICT-0001"


def test_valid_signature_cannot_smuggle_amount(client):
    payload = _payload()
    body = {"payload": payload, "signature": sign_payload(ESIGN_SECRET, payload),
            "amount_cents": 1}
    resp = client.post("/api/sales/esign/callback", json=body)
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "READONLY_FIELD"


def test_secret_must_come_from_env(client, monkeypatch):
    monkeypatch.delenv("ESIGN_SECRET", raising=False)
    payload = _payload()
    body = {"payload": payload, "signature": sign_payload(ESIGN_SECRET, payload)}
    resp = client.post("/api/sales/esign/callback", json=body)
    assert resp.status_code == 500
    assert resp.json()["detail"]["code"] == "ESIGN_SECRET_MISSING"
