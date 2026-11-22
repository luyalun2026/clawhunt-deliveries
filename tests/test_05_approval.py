# -*- coding: utf-8 -*-
"""⑤ 审批：自批拒绝、跳步拒绝、角色与步骤不匹配拒绝、两步正常通过。"""
import pytest

from tests.helpers import H, fin, obj_id, user

OWNER = user("a", 1, "c1")
SUP = user("a", 1, "sup")
FIN = fin("a")


def _submitted_quote(client, actor=OWNER):
    created = client.post("/api/sales/quotes",
                          json={"lead_id": obj_id("lead", actor if actor != SUP else OWNER),
                                "unit_type": "office", "lease_months": 12},
                          headers=H(actor))
    assert created.status_code == 200, created.text
    qid = created.json()["id"]
    sub = client.post("/api/sales/quotes/%s/submit" % qid, headers=H(actor))
    assert sub.status_code == 200, sub.text
    return qid


def test_happy_path_two_steps(client):
    qid = _submitted_quote(client)
    first = client.post("/api/sales/quotes/%s/approve" % qid, json={"step": 0}, headers=H(SUP))
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "pending_approval"
    second = client.post("/api/sales/quotes/%s/approve" % qid, json={"step": 1}, headers=H(FIN))
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "approved"
    assert second.json()["approval_steps"][0]["decided_by"] == SUP


def test_self_approval_rejected(client):
    qid = _submitted_quote(client, actor=SUP)
    resp = client.post("/api/sales/quotes/%s/approve" % qid, json={"step": 0}, headers=H(SUP))
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "SELF_APPROVAL"


def test_skip_step_rejected(client):
    qid = _submitted_quote(client)
    resp = client.post("/api/sales/quotes/%s/approve" % qid, json={"step": 1}, headers=H(FIN))
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "STEP_ORDER"


def test_role_step_mismatch_rejected(client):
    qid = _submitted_quote(client)
    assert client.post("/api/sales/quotes/%s/approve" % qid, json={"step": 0},
                       headers=H(SUP)).status_code == 200
    resp = client.post("/api/sales/quotes/%s/approve" % qid, json={"step": 1}, headers=H(SUP))
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "ROLE_MISMATCH"


def test_other_consultant_cannot_approve(client):
    qid = _submitted_quote(client)
    resp = client.post("/api/sales/quotes/%s/approve" % qid, json={"step": 0},
                       headers=H(user("a", 1, "c3")))
    assert resp.status_code == 404


def test_finance_cannot_submit_for_owner(client):
    qid = _submitted_quote(client)
    resp = client.post("/api/sales/quotes/%s/submit" % qid, headers=H(FIN))
    assert resp.status_code == 403


def test_locked_quote_cannot_be_edited_after_submit(client):
    qid = _submitted_quote(client)
    resp = client.put("/api/sales/quotes/%s" % qid, json={"lease_months": 36}, headers=H(OWNER))
    assert resp.status_code == 409
