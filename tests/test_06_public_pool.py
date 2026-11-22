# -*- coding: utf-8 -*-
"""⑥ 公海脱敏：响应中匹配不到 11 位连续数字的手机号。"""
import re

from tests.helpers import H, ORG, user

PHONE_11 = re.compile(r"(?<!\d)\d{11}(?!\d)")


def test_public_pool_has_no_full_phone(client):
    resp = client.get("/api/sales/public-pool", headers=H(user("a", 1, "c1")))
    assert resp.status_code == 200
    body = resp.text
    assert PHONE_11.search(body) is None, PHONE_11.search(body).group(0)
    items = resp.json()["items"]
    assert items
    for item in items:
        assert item["org_id"] if "org_id" in item else True
        assert "****" in item["phone_masked"]
        assert len(item["phone_masked"]) == 11
        assert PHONE_11.search(item["phone_masked"]) is None


def test_public_pool_is_org_scoped(client):
    resp = client.get("/api/sales/public-pool", headers=H(user("b", 1, "c1")))
    ids = {i["id"] for i in resp.json()["items"]}
    assert len(ids) == 1
    # org B 只看到自己的公海线索，看不到 org A 的
    a_resp = client.get("/api/sales/public-pool", headers=H(user("a", 1, "c1")))
    assert not (ids & {i["id"] for i in a_resp.json()["items"]})


def test_public_pool_hides_owner_and_budget(client):
    resp = client.get("/api/sales/public-pool", headers=H(user("a", 1, "c1")))
    for item in resp.json()["items"]:
        assert set(item) == {"id", "name", "company", "site_id", "status", "phone_masked"}
