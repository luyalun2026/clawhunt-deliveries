# -*- coding: utf-8 -*-
"""模型扫描（AC 范围③）：会员端 Pydantic 响应模型出现禁键字段名时测试失败。

模型清单不再手工维护：由 `app.model_scan.discover_response_models` 从 FastAPI 路由
（`/api/mini/` 下的 GET 接口及其嵌套模型）自动发现，新增接口无需登记即被扫描。
"""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from app.assertions import BANNED_KEYS
from app.main import app as mini_app
from app.model_scan import banned_hits, discover_response_models


def test_discovery_finds_expected_models():
    """自动发现应覆盖当前全部会员端响应模型（含 list[...] 包装）。"""
    models = discover_response_models(mini_app)
    assert {"CompanyOut", "ContactOut", "NoticeOut", "ProfileOut", "StreetOut", "PointOut"} <= set(models)
    assert len(models) >= 6


def test_no_response_model_contains_banned_field():
    models = discover_response_models(mini_app)
    hits = banned_hits(models, BANNED_KEYS)
    assert hits == [], f"响应模型含禁键字段：{hits}"


def test_new_route_without_registration_is_scanned():
    """临时新增一个含禁键的会员端 GET 接口，不登记任何清单，也应被发现。"""
    probe = FastAPI()

    class LeakyOut(BaseModel):
        id: str
        phone: str          # 禁键

    @probe.get("/api/mini/probe/leaky", response_model=list[LeakyOut])
    def _leaky():          # pragma: no cover - 仅用于路由发现
        return []

    models = discover_response_models(probe)
    assert "LeakyOut" in models, "新增接口的响应模型未被自动发现"
    assert banned_hits(models, BANNED_KEYS) == ["LeakyOut.phone"]


def test_nested_model_is_scanned():
    """嵌套模型同样自动纳入扫描。"""
    probe = FastAPI()

    class Inner(BaseModel):
        email: str          # 禁键

    class Outer(BaseModel):
        id: str
        inner: Inner
        items: list[Inner]

    @probe.get("/api/mini/probe/nested", response_model=Outer)
    def _nested():         # pragma: no cover
        return {}

    models = discover_response_models(probe)
    assert {"Outer", "Inner"} <= set(models)
    assert "Inner.email" in banned_hits(models, BANNED_KEYS)


def test_profile_contact_visible_is_bool_only():
    """profile 的 contact_visible 只允许布尔值，不能携带联系方式本体。"""
    from app.main import ProfileOut
    f = ProfileOut.model_fields["contact_visible"]
    assert f.annotation is bool
