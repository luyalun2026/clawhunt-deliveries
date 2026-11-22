# -*- coding: utf-8 -*-
"""负向证据测试（不在主套件中运行）：对破坏版应用跑同一套断言，必须失败。

verify.py 以 `pytest tests_negative` 且「预期非零退出码」运行本目录，
失败输出转录保存至 outputs/，作为 AC #2 / AC #3 的证据。
"""
from __future__ import annotations

import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG_ROOT))

from fastapi.testclient import TestClient

from app.assertions import assert_no_contact, assert_street_level_coord
from app.broken_app import broken_app
from app.seed import CANARY_COMPANIES, MAP_STREETS, all_canary_values

client = TestClient(broken_app)
CANARY = all_canary_values()


def test_injected_phone_must_fail():
    """AC #2：故意在会员端响应中加入 phone 字段后测试失败。"""
    r = client.get(f"/api/mini/companies/{CANARY_COMPANIES[0]['id']}")
    assert r.status_code == 200
    # 同一套断言对违规响应必须抛错
    assert_no_contact(r.json(), CANARY)
    raise AssertionError("本行不应到达：phone 注入未被断言拦截")


def test_precise_coord_must_fail():
    """AC #3：故意在地图点位中返回非街道中心点坐标后测试失败。"""
    r = client.get("/api/mini/map/streets/st-0101/points")
    assert r.status_code == 200
    assert_street_level_coord(r.json(), MAP_STREETS)
    raise AssertionError("本行不应到达：高精度坐标未被断言拦截")
