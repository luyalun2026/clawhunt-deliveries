# -*- coding: utf-8 -*-
"""故意违规的破坏版应用（仅用于产出 AC #2/#3 的“测试失败”证据）：

  ① 在企业详情响应中注入禁键 phone；
  ② 在地图点位响应中返回高精度非街道中心坐标。
"""
from __future__ import annotations

from fastapi import FastAPI

from .seed import CANARY_COMPANIES, MAP_POINTS, STREET_BY_ID

broken_app = FastAPI(title="broken-variant-for-negative-evidence")


@broken_app.get("/api/mini/companies/{company_id}")
def get_company(company_id: str):
    for c in CANARY_COMPANIES:
        if c["id"] == company_id:
            # ★ 违规注入：直接下发禁键 phone（金丝雀值）
            return {"id": c["id"], "name": c["name"], "phone": c["mobile"]}
    return {"error": "not found"}


@broken_app.get("/api/mini/map/streets/{street_id}/points")
def street_points(street_id: str):
    street = STREET_BY_ID.get(street_id)
    if street is None:
        return []
    # ★ 违规注入：下发点位“真实”高精度坐标（非街道中心点、小数远超 4 位）
    return [
        {"id": p["id"], "name": p["name"], "street_id": p["street_id"],
         "lat": p["raw_lat"], "lng": p["raw_lng"]}
        for p in MAP_POINTS if p["street_id"] == street_id
    ]
