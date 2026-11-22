# -*- coding: utf-8 -*-
"""② 越权写入：6 类对象的全部写接口（PUT / PATCH / POST 动作）逐个断言
404 或 403，且写入前后对象快照完全一致（数据未变化）。"""
import copy

import pytest

from tests.helpers import H, KINDS, fin as finance_id, obj_id, user

VICTIM = user("a", 1, "c1")
ATTACKER = user("a", 1, "c2")

CASES = [
    ("PUT", "/api/sales/leads/{lead_id}"),
    ("PATCH", "/api/sales/leads/{lead_id}"),
    ("POST", "/api/sales/leads/{lead_id}/assign"),
    ("POST", "/api/sales/followups"),
    ("PUT", "/api/sales/followups/{item_id}"),
    ("PATCH", "/api/sales/followups/{item_id}"),
    ("POST", "/api/sales/visits"),
    ("PUT", "/api/sales/visits/{item_id}"),
    ("PATCH", "/api/sales/visits/{item_id}"),
    ("POST", "/api/sales/quotes"),
    ("PUT", "/api/sales/quotes/{item_id}"),
    ("PATCH", "/api/sales/quotes/{item_id}"),
    ("POST", "/api/sales/quotes/{item_id}/submit"),
    ("POST", "/api/sales/quotes/{item_id}/approve"),
    ("PATCH", "/api/sales/contracts/{item_id}"),
    ("POST", "/api/sales/contracts/{item_id}/sign"),
    ("POST", "/api/sales/attachments"),
    ("POST", "/api/sales/attachments/presign"),
]

COLLS = ("leads", "followups", "visits", "quotes", "contracts", "attachments")


def _path(path):
    if "{lead_id}" in path:
        return path.replace("{lead_id}", obj_id("lead", VICTIM))
    if "{item_id}" not in path:
        return path
    for kind in ("followup", "visit", "quote", "contract", "attachment"):
        if "/%ss/" % kind in path:
            return path.replace("{item_id}", obj_id(kind, VICTIM))
    raise AssertionError("未覆盖的路径模板: %s" % path)


def _body(path):
    if path.endswith("/assign"):
        return {"owner_id": ATTACKER}
    if path.endswith("/approve"):
        return {"step": 0}
    if path.endswith("/presign"):
        return {"attachment_id": obj_id("attachment", VICTIM)}
    if path in ("/api/sales/followups", "/api/sales/visits"):
        return {"lead_id": obj_id("lead", VICTIM), "note": "越权写入尝试"}
    if path == "/api/sales/quotes":
        return {"lead_id": obj_id("lead", VICTIM), "unit_type": "office", "lease_months": 12}
    if path == "/api/sales/attachments":
        return {"quote_id": obj_id("quote", VICTIM), "filename": "x.pdf"}
    return {"name": "越权改名", "note": "越权写入尝试", "status": "closed"}


def _snapshot(db):
    return copy.deepcopy({
        coll: {k: v for k, v in db[coll].items() if v["owner_id"] == VICTIM}
        for coll in COLLS
    })


@pytest.mark.parametrize("method,path", CASES, ids=["%s %s" % c for c in CASES])
def test_write_other_object_rejected(client, db, method, path):
    before = _snapshot(db)
    url = _path(path)
    resp = client.request(method, url, json=_body(path), headers=H(ATTACKER))
    assert resp.status_code in (403, 404), (method, url, resp.status_code, resp.text)
    assert _snapshot(db) == before, "越权写入改变了数据: %s %s" % (method, url)


def test_supervisor_can_write_within_site_but_not_other_site(client):
    sup = user("a", 1, "sup")
    own_site = client.patch("/api/sales/leads/%s" % obj_id("lead", VICTIM),
                            json={"status": "visit_booked"}, headers=H(sup))
    assert own_site.status_code == 200
    other_sup = user("a", 2, "sup")
    cross = client.patch("/api/sales/leads/%s" % obj_id("lead", VICTIM),
                         json={"status": "closed"}, headers=H(other_sup))
    assert cross.status_code == 404


def test_finance_role_is_read_only(client):
    resp = client.patch("/api/sales/leads/%s" % obj_id("lead", VICTIM),
                        json={"status": "closed"}, headers=H(finance_id("a")))
    assert resp.status_code == 403
    read = client.get("/api/sales/leads/%s" % obj_id("lead", VICTIM),
                      headers=H(finance_id("a")))
    assert read.status_code == 200


def test_anonymous_is_401(client):
    resp = client.get("/api/sales/leads")
    assert resp.status_code == 401
