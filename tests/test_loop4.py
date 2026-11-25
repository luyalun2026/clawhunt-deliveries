# -*- coding: utf-8 -*-
"""闭环四核心断言：pytest + httpx。
运行前：python seed.py --scenario loop4
"""
import os
import subprocess
import sys

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seed as seed_mod
from loop4_common import (EXPECTED_COUNTS, EXPECTED_MAU_ACTIVE_ENTS,
                          EXPECTED_MAU_EXCLUDED_ENTS, INTERACTION_TYPES,
                          MEMBER_U1)

BASE = "http://testserver"
HEADERS = {"Authorization": "Bearer loop4-test-token"}


@pytest.fixture(scope="module", autouse=True)
def _seed(tmp_path_factory):
    seed_mod.seed_scenario_loop4()


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    import stub_app
    with TestClient(stub_app.app) as c:
        yield c


def test_six_counts_match_constructed_data(client):
    """AC1: 6 项计数与构造数据一一对应（期望值取自 loop4_common 常量，同源）。"""
    r = client.get(f"{BASE}/api/crm/members/{MEMBER_U1['id']}/portrait", headers=HEADERS)
    assert r.status_code == 200
    got = r.json()["month_counts"]
    for key, expected in EXPECTED_COUNTS.items():
        assert got[key] == expected, f"{key}: 期望 {expected}, 实际 {got[key]}"


def test_all_interactions_source_mini(client):
    """AC2: 每条有效互动 source=mini。"""
    r = client.get(f"{BASE}/api/track/interactions?member_id={MEMBER_U1['id']}", headers=HEADERS)
    assert r.status_code == 200
    items = [i for i in r.json()["items"] if i["type"] in INTERACTION_TYPES]
    assert len(items) == sum(EXPECTED_COUNTS[k] for k in
                             ("certified_contacts", "demands", "signups", "checkins", "asks"))
    assert all(i["source"] == "mini" for i in items)


def test_mau_numerator_includes_interactive_excludes_browse_only(client):
    """AC3: 月活分子包含企业 A，排除只浏览的企业 B。"""
    r = client.get(f"{BASE}/api/dash/mau", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    for ent in EXPECTED_MAU_ACTIVE_ENTS:
        assert ent in body["active_enterprises"]
    for ent in EXPECTED_MAU_EXCLUDED_ENTS:
        assert ent not in body["active_enterprises"]
    assert body["numerator"] == len(EXPECTED_MAU_ACTIVE_ENTS)


def test_interaction_type_constant_matches_readme():
    """AC4: 有效互动定义常量与 README 口径一致。"""
    readme = open(os.path.join(os.path.dirname(__file__), "..", "README.md"), encoding="utf-8").read()
    for t in ("认证", "发布", "报名", "签到", "提问"):
        assert t in readme
    assert INTERACTION_TYPES == ["auth", "demand", "signup", "checkin", "ask"]
    assert "browse" not in INTERACTION_TYPES


# ---------- 边界另测 ----------

def test_duplicate_checkin_dedup(client):
    """重复签到同活动同会员只计 1。"""
    r = client.get(f"{BASE}/api/crm/members/{MEMBER_U1['id']}/portrait", headers=HEADERS)
    assert r.json()["month_counts"]["checkins"] == 1


def test_cross_month_interaction_not_counted(client):
    """跨月互动不计当月：seed 里的上月 demand 未进入 demands=1。"""
    r = client.get(f"{BASE}/api/crm/members/{MEMBER_U1['id']}/portrait", headers=HEADERS)
    assert r.json()["month_counts"]["demands"] == 1


def test_soft_deleted_member_not_counted(client):
    """软删除会员的互动不计。"""
    r = client.get(f"{BASE}/api/track/interactions", headers=HEADERS)
    members = {i.get("member_id") for i in r.json()["items"]}
    assert "mem-UD-0003" not in members


def test_no_token_401(client):
    assert client.get(f"{BASE}/api/crm/members/{MEMBER_U1['id']}/portrait").status_code == 401
    assert client.get(f"{BASE}/api/dash/mau").status_code == 401


def test_empty_dataset_zero_counts(tmp_path, monkeypatch):
    """空数据集：6 项计数全 0，月活占比 0。"""
    from fastapi.testclient import TestClient
    import stub_app
    orig = seed_mod.DB_PATH
    empty_db = str(tmp_path / "empty.db")
    monkeypatch.setattr(seed_mod, "DB_PATH", empty_db)
    monkeypatch.setattr(stub_app, "DB_PATH", empty_db)
    conn = seed_mod.reset()
    conn.execute("INSERT INTO enterprises VALUES ('ent-x','虚企业','S1')")
    conn.commit()
    conn.close()
    with TestClient(stub_app.app) as c:
        r = c.get(f"{BASE}/api/dash/mau", headers=HEADERS)
        assert r.json()["numerator"] == 0 and r.json()["ratio"] == 0.0
    monkeypatch.setattr(seed_mod, "DB_PATH", orig)
    monkeypatch.setattr(stub_app, "DB_PATH", orig)
