# -*- coding: utf-8 -*-
"""模型扫描（AC 范围③）：会员端 Pydantic 响应模型出现禁键字段名时测试失败。"""
from __future__ import annotations

from app.assertions import BANNED_KEYS
from app.main import (
    CompanyOut,
    ContactOut,
    NoticeOut,
    PointOut,
    ProfileOut,
    StreetOut,
)

RESPONSE_MODELS = [CompanyOut, ContactOut, NoticeOut, ProfileOut, StreetOut, PointOut]


def test_no_response_model_contains_banned_field():
    hits = []
    for m in RESPONSE_MODELS:
        for fname in m.model_fields:
            if fname in BANNED_KEYS:
                hits.append(f"{m.__name__}.{fname}")
    assert hits == [], f"响应模型含禁键字段：{hits}"


def test_all_mini_response_models_are_registered():
    """防漏网：显式核对模型清单与 /api/mini/ 响应模型一致（新增接口须登记）。"""
    assert len(RESPONSE_MODELS) == 6
    names = {m.__name__ for m in RESPONSE_MODELS}
    assert names == {"CompanyOut", "ContactOut", "NoticeOut", "ProfileOut", "StreetOut", "PointOut"}


def test_profile_contact_visible_is_bool_only():
    """profile 的 contact_visible 只允许布尔值，不能携带联系方式本体。"""
    f = ProfileOut.model_fields["contact_visible"]
    assert f.annotation is bool
