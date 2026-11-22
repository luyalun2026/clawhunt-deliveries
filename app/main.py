# -*- coding: utf-8 -*-
"""会员端 FastAPI 应用（接口桩形态：内存数据，无外部依赖）。

设计要点：
  * 内部数据（seed.py）持有金丝雀联系方式与高精度坐标；
  * 全部 /api/mini/ 响应经 Pydantic 响应模型过滤 —— 模型中不含禁键字段，
    坐标一律替换为所在街道中心点（4 位小数）；
  * 4 种身份：guest（无头）/ none（已登录未认证）/ member / admin，
    由请求头 X-Auth-Role 携带，缺失视为 guest。
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

from .seed import CANARY_COMPANIES, CANARY_CONTACTS, MAP_POINTS, MAP_STREETS, MEMBERS, NOTICES, STREET_BY_ID

app = FastAPI(
    title="会员空间平台 · 会员端接口桩",
    description="S3-MINI-045 脱敏自动化测试对象（虚构数据）",
    version="1.0.0",
)

Role = Literal["guest", "none", "member", "admin"]

VALID_ROLES = {"guest", "none", "member", "admin"}


def get_role(x_auth_role: Optional[str]) -> str:
    if x_auth_role is None or x_auth_role == "":
        return "guest"
    if x_auth_role not in VALID_ROLES:
        raise HTTPException(status_code=401, detail="未知身份")
    return x_auth_role


# ---------- 响应模型（模型扫描对象：不得含禁键字段） ----------

class CompanyOut(BaseModel):
    id: str
    name: str
    industry: str
    street_id: str


class ContactOut(BaseModel):
    id: str
    company_id: str
    name: str  # 仅展示姓名；联系方式字段一律不下发


class NoticeOut(BaseModel):
    id: str
    title: str
    body: str
    published_at: str


class ProfileOut(BaseModel):
    id: str
    display_name: str
    company_name: str
    role: str
    contact_visible: bool = False  # 布尔标记，不含联系方式本体


class StreetOut(BaseModel):
    id: str
    name: str
    lat: float
    lng: float


class PointOut(BaseModel):
    id: str
    name: str
    street_id: str
    lat: float  # = 街道中心点
    lng: float


# ---------- 接口 ----------

@app.get("/api/mini/companies", response_model=list[CompanyOut], tags=["企业"])
def list_companies(x_auth_role: Optional[str] = Header(default=None)):
    get_role(x_auth_role)
    return [
        {"id": c["id"], "name": c["name"], "industry": c["industry"], "street_id": c["street_id"]}
        for c in CANARY_COMPANIES
    ]


@app.get("/api/mini/companies/{company_id}", response_model=CompanyOut, tags=["企业"])
def get_company(company_id: str, x_auth_role: Optional[str] = Header(default=None)):
    get_role(x_auth_role)
    for c in CANARY_COMPANIES:
        if c["id"] == company_id:
            return {"id": c["id"], "name": c["name"], "industry": c["industry"], "street_id": c["street_id"]}
    raise HTTPException(status_code=404, detail="企业不存在")


@app.get("/api/mini/companies/{company_id}/contacts", response_model=list[ContactOut], tags=["企业"])
def list_company_contacts(company_id: str, x_auth_role: Optional[str] = Header(default=None)):
    get_role(x_auth_role)
    return [
        {"id": ct["id"], "company_id": ct["company_id"], "name": ct["name"]}
        for ct in CANARY_CONTACTS if ct["company_id"] == company_id
    ]


@app.get("/api/mini/notices", response_model=list[NoticeOut], tags=["公告"])
def list_notices(x_auth_role: Optional[str] = Header(default=None)):
    get_role(x_auth_role)
    return NOTICES


@app.get("/api/mini/notices/{notice_id}", response_model=NoticeOut, tags=["公告"])
def get_notice(notice_id: str, x_auth_role: Optional[str] = Header(default=None)):
    get_role(x_auth_role)
    for n in NOTICES:
        if n["id"] == notice_id:
            return n
    raise HTTPException(status_code=404, detail="公告不存在")


@app.get("/api/mini/profile", response_model=ProfileOut, tags=["会员"])
def get_profile(x_auth_role: Optional[str] = Header(default=None)):
    role = get_role(x_auth_role)
    if role in ("guest", "none"):
        raise HTTPException(status_code=401, detail="未认证")
    m = MEMBERS["mb-0002"] if role == "admin" else MEMBERS["mb-0001"]
    company = next(c for c in CANARY_COMPANIES if c["id"] == m["company_id"])
    return {
        "id": m["id"], "display_name": m["display_name"],
        "company_name": company["name"], "role": m["role"], "contact_visible": False,
    }


@app.get("/api/mini/map/streets", response_model=list[StreetOut], tags=["地图"])
def list_streets(x_auth_role: Optional[str] = Header(default=None)):
    get_role(x_auth_role)
    return MAP_STREETS


@app.get("/api/mini/map/streets/{street_id}/points", response_model=list[PointOut], tags=["地图"])
def street_points(street_id: str, x_auth_role: Optional[str] = Header(default=None)):
    get_role(x_auth_role)
    street = STREET_BY_ID.get(street_id)
    if street is None:
        raise HTTPException(status_code=404, detail="街道不存在")
    return [
        {"id": p["id"], "name": p["name"], "street_id": p["street_id"],
         "lat": street["lat"], "lng": street["lng"]}
        for p in MAP_POINTS if p["street_id"] == street_id
    ]


@app.get("/api/mini/map/nearby", response_model=list[StreetOut], tags=["地图"])
def nearby_streets(
    lat: float = Query(...), lng: float = Query(...),
    x_auth_role: Optional[str] = Header(default=None),
):
    get_role(x_auth_role)
    ordered = sorted(
        MAP_STREETS,
        key=lambda s: (s["lat"] - lat) ** 2 + (s["lng"] - lng) ** 2,
    )
    return ordered[:3]
