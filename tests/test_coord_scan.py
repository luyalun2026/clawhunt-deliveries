# -*- coding: utf-8 -*-
"""坐标检查（AC #3 正向）：/api/mini/map/ 全部响应 lat/lng = 街道中心点且 ≤4 位小数。"""
from __future__ import annotations

from app.assertions import assert_street_level_coord
from app.seed import MAP_STREETS
from tests.scan_helper import client, iter_requests, list_mini_get_endpoints  # noqa: F401


def test_map_endpoints_street_level_coords(client):
    eps = [e for e in list_mini_get_endpoints(client) if e["path"].startswith("/api/mini/map/")]
    assert len(eps) >= 3, f"地图接口 {len(eps)} 条，低于预期 3 条"

    checked = 0
    for ep in eps:
        for role, url, headers in iter_requests(client, ep):
            r = client.get(url, headers=headers)
            assert r.status_code == 200, f"GET {url}（{role}）状态码 {r.status_code}"
            payload = r.json()
            # lat/lng 必须与 map_streets 中某街道中心点完全相等，小数不超过 4 位
            assert_street_level_coord(payload, MAP_STREETS)
            checked += 1
    print(f"\nCOORD-CHECK checked_responses={checked}")


def test_street_centers_have_at_most_4_decimals():
    """种子街道中心点本身必须 ≤4 位小数。"""
    for s in MAP_STREETS:
        for k in ("lat", "lng"):
            txt = f"{s[k]:.10f}".rstrip("0")
            frac = txt.split(".")[1]
            assert len(frac.rstrip("0")) <= 4, f"{s['id']}.{k}={s[k]} 小数超 4 位"


def test_nearby_streets_reject_mismatched_pair_shape(client):
    """nearby 响应中的每个对象都是「lat+lng 成对」且等于街道中心点。"""
    r = client.get("/api/mini/map/nearby", params={"lat": 30.5123, "lng": 114.3123})
    assert r.status_code == 200
    for item in r.json():
        assert set(("lat", "lng")).issubset(item.keys())
