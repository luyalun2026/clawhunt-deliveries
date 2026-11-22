# -*- coding: utf-8 -*-
"""③ 跨 org：任何角色访问另一 org 的对象返回 404；列表接口按 org 隔离。"""
import pytest

from tests.helpers import H, KINDS, ORG, fin, obj_id, user

LISTS = [
    ("/api/sales/leads", "leads"),
    ("/api/sales/followups", "followups"),
    ("/api/sales/visits", "visits"),
    ("/api/sales/quotes", "quotes"),
    ("/api/sales/contracts", "contracts"),
    ("/api/sales/attachments", "attachments"),
]
PATHS = {
    "lead": "/api/sales/leads/%s",
    "followup": "/api/sales/followups/%s",
    "visit": "/api/sales/visits/%s",
    "quote": "/api/sales/quotes/%s",
    "contract": "/api/sales/contracts/%s",
    "attachment": "/api/sales/attachments/%s",
}
ROLES = [("consultant", user("b", 1, "c1")), ("supervisor", user("b", 1, "sup")),
         ("finance", fin("b"))]


@pytest.mark.parametrize("kind", KINDS)
def test_cross_org_read_404(client, kind):
    victim = user("a", 1, "c1")
    for label, actor in ROLES:
        resp = client.get(PATHS[kind] % obj_id(kind, victim), headers=H(actor))
        assert resp.status_code == 404, (kind, label, resp.status_code)


@pytest.mark.parametrize("path,coll", LISTS, ids=[c[1] for c in LISTS])
def test_list_endpoints_are_org_scoped(client, db, path, coll):
    actor_b = user("b", 1, "c1")
    resp = client.get(path, headers=H(actor_b))
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items, "org B 应能看到自己的数据"
    for item in items:
        assert item["org_id"] == ORG["b"]
    victim_ids = {obj_id(k, user("a", 1, "c1")) for k in KINDS}
    assert not (victim_ids & {i["id"] for i in items})


def test_cross_org_write_404_and_no_change(client, db):
    victim = user("a", 1, "c1")
    attacker = user("b", 1, "c1")
    lead_id = obj_id("lead", victim)
    before = dict(db["leads"][lead_id])
    resp = client.patch("/api/sales/leads/%s" % lead_id,
                        json={"status": "closed"}, headers=H(attacker))
    assert resp.status_code == 404
    assert db["leads"][lead_id] == before
