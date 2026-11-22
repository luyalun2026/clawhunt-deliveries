# -*- coding: utf-8 -*-
"""⑦ 附件预签名：返回的链接本身受 300 秒 TTL 约束，过期即 410。"""
from app import clock
from tests.helpers import H, obj_id, user

OWNER = user("a", 1, "c1")


def _presign(client):
    resp = client.post("/api/sales/attachments/presign",
                       json={"attachment_id": obj_id("attachment", OWNER)}, headers=H(OWNER))
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_presigned_link_expires_after_5_minutes(client):
    data = _presign(client)
    assert data["expires_in"] == 300
    url = data["url"]

    ok = client.get(url, headers=H(OWNER))
    assert ok.status_code == 200, ok.text
    assert ok.json()["filename"].endswith(".pdf")

    clock.advance(299)
    still_ok = client.get(url, headers=H(OWNER))
    assert still_ok.status_code == 200

    clock.advance(2)          # 累计 301 秒 > 300 秒 TTL
    expired = client.get(url, headers=H(OWNER))
    assert expired.status_code == 410
    assert expired.json()["detail"]["code"] == "PRESIGN_EXPIRED"


def test_tampered_token_rejected(client):
    data = _presign(client)
    url = data["url"].split("token=")[0] + "token=deadbeef"
    resp = client.get(url, headers=H(OWNER))
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "PRESIGN_INVALID"


def test_presign_other_consultant_attachment_is_404(client):
    victim = user("a", 1, "c1")
    attacker = user("a", 1, "c2")
    resp = client.post("/api/sales/attachments/presign",
                       json={"attachment_id": obj_id("attachment", victim)}, headers=H(attacker))
    assert resp.status_code == 404
