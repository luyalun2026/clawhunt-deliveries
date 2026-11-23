# -*- coding: utf-8 -*-
"""assert_no_contact 独立单测（AC #4）：覆盖嵌套对象与数组两种结构。"""
from __future__ import annotations

import pytest

from app.assertions import (
    assert_no_contact,
    find_contact_violations,
    find_coord_violations,
)
from app.seed import MAP_STREETS, all_canary_values

CANARY = all_canary_values()


# ---------- 嵌套对象结构 ----------

def test_nested_object_banned_key_detected():
    payload = {"data": {"profile": {"phone": "000-0000"}}}
    with pytest.raises(AssertionError) as e:
        assert_no_contact(payload, CANARY)
    assert "禁键「phone」" in str(e.value)
    assert "$.data.profile.phone" in str(e.value)


def test_callable_with_payload_only():
    """按本单原文可直接 assert_no_contact(payload) 调用（金丝雀值取默认全集）。"""
    assert_no_contact({"data": {"name": "正常文本"}})          # 干净数据：不抛
    with pytest.raises(AssertionError):
        assert_no_contact({"data": {"phone": "000-0000"}})     # 禁键仍被拦
    canary = CANARY[0]
    with pytest.raises(AssertionError) as e:
        assert_no_contact({"data": {"note": canary}})           # 默认全集包含该金丝雀
    assert "金丝雀值泄露" in str(e.value)


def test_deeply_nested_object_clean_passes():
    payload = {"a": {"b": {"c": [{"d": "普通文本"}]}}}
    assert_no_contact(payload, CANARY)  # 不抛即通过


def test_nested_object_canary_value_detected():
    canary = CANARY[0]
    payload = {"list": {"item": {"note": canary}}}
    violations = find_contact_violations(payload, CANARY)
    assert any("金丝雀值泄露" in v for v in violations)


def test_nested_object_mobile_regex_detected():
    payload = {"a": {"b": "联系方式 13912345678 请来电"}}
    violations = find_contact_violations(payload, [])
    assert any("手机号正则" in v for v in violations)


def test_nested_object_email_regex_detected():
    payload = {"a": {"b": "发送到 someone@example.com 即可"}}
    violations = find_contact_violations(payload, [])
    assert any("邮箱正则" in v for v in violations)


def test_nested_object_clean_phone_like_text_not_flagged():
    """11 位数字以外形态（订单号等）不应误报。"""
    payload = {"order": "20261121-000123"}
    assert find_contact_violations(payload, []) == []


# ---------- 数组结构 ----------

def test_array_of_objects_banned_key_detected():
    payload = {"items": [{"id": "1"}, {"mobile": "000"}]}
    with pytest.raises(AssertionError) as e:
        assert_no_contact(payload, CANARY)
    assert "禁键「mobile」" in str(e.value)
    assert "$.items[1].mobile" in str(e.value)


def test_array_of_strings_canary_detected():
    # 选用微信号形态金丝雀（不被手机/邮箱/座机正则命中），验证数组下标路径
    canary = "wx_fake_0001"
    payload = {"tags": ["普通", canary]}
    violations = find_contact_violations(payload, CANARY)
    assert len(violations) == 1
    assert "$.tags[1]" in violations[0]
    assert "金丝雀值泄露" in violations[0]


def test_nested_array_in_object_multiple_violations_counted():
    payload = {
        "outer": {
            "rows": [
                {"email": "000"},                    # 禁键（值 "000" 不命中任何正则）
                {"note": "wx_fake_0001"},            # 金丝雀（微信号不命中正则）
                {"memo": "联系 13612345678"},        # 手机号正则
            ]
        }
    }
    violations = find_contact_violations(payload, CANARY)
    assert len(violations) == 3
    assert any("禁键「email」" in v for v in violations)
    assert any("金丝雀值泄露" in v for v in violations)
    assert any("手机号正则" in v for v in violations)
    with pytest.raises(AssertionError) as e:
        assert_no_contact(payload, CANARY)
    assert "共 3 处违规" in str(e.value)


def test_empty_containers_pass():
    assert_no_contact({"a": {}, "b": [], "c": [{"d": []}]}, CANARY)


# ---------- 坐标断言独立单测 ----------

def test_coord_non_center_detected():
    payload = [{"lat": 30.51234, "lng": 114.31234}]  # 非街道中心点
    violations = find_coord_violations(payload, MAP_STREETS)
    assert any("不等于任何街道中心点" in v for v in violations)


def test_coord_over_four_decimals_detected():
    payload = [{"lat": 30.512301, "lng": 114.3123}]  # 小数 6 位
    violations = find_coord_violations(payload, MAP_STREETS)
    assert any("超过 4 位" in v for v in violations)


def test_coord_exact_center_passes():
    assert find_coord_violations([{"lat": 30.5123, "lng": 114.3123}], MAP_STREETS) == []
