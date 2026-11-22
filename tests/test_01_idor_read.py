# -*- coding: utf-8 -*-
"""① 越权读取：同会所其他顾问 / 跨会所 / 跨 org，逐个按 id GET 全部 404。"""
import pytest

from tests.helpers import H, KINDS, obj_id, user

PATHS = {
    "lead": "/api/sales/leads/%s",
    "followup": "/api/sales/followups/%s",
    "visit": "/api/sales/visits/%s",
    "quote": "/api/sales/quotes/%s",
    "contract": "/api/sales/contracts/%s",
    "attachment": "/api/sales/attachments/%s",
}
ATTACKERS = [
    ("same_site_consultant", user("a", 1, "c2")),
    ("same_org_other_site", user("a", 2, "c1")),
    ("other_site_supervisor", user("a", 2, "sup")),
]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("label,attacker", ATTACKERS, ids=[a[0] for a in ATTACKERS])
def test_read_other_consultant_object_404(client, kind, label, attacker):
    victim = user("a", 1, "c1")
    resp = client.get(PATHS[kind] % obj_id(kind, victim), headers=H(attacker))
    assert resp.status_code == 404, (kind, label, resp.status_code, resp.text)


def test_owner_can_read_own_objects(client):
    owner = user("a", 1, "c1")
    for kind in KINDS:
        resp = client.get(PATHS[kind] % obj_id(kind, owner), headers=H(owner))
        assert resp.status_code == 200, (kind, resp.text)


def test_missing_object_is_404_not_500(client):
    resp = client.get("/api/sales/leads/does-not-exist", headers=H(user("a", 1, "c1")))
    assert resp.status_code == 404
