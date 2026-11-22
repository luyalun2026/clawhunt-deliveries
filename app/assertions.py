# -*- coding: utf-8 -*-
"""可复用脱敏断言：assert_no_contact(payload) 与街道级坐标断言。

两条硬规则：
  R1 任何 /api/mini/ 接口响应中不得出现联系方式（金丝雀值 / 禁键 / 手机号·邮箱正则）。
  R2 /api/mini/map/ 响应中的 lat/lng 必须与 map_streets 中某街道中心点完全相等，
     且小数不超过 4 位。
"""
from __future__ import annotations

import re
from typing import Any

# 禁止出现在响应中的键名（AC：名为 phone/mobile/tel/email/wechat/wx_id/contact 的键）
BANNED_KEYS = ("phone", "mobile", "tel", "email", "wechat", "wx_id", "contact")

# 手机号（中国大陆 11 位）与邮箱正则：任何字符串命中即视为联系方式泄露
MOBILE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9])"
)

# 座机（区号-号码，金丝雀形态之一）
LANDLINE_RE = re.compile(r"(?<!\d)0\d{2,3}-\d{7,8}(?!\d)")


def _walk(obj: Any, path: str, cb) -> None:
    """递归遍历 JSON（覆盖嵌套对象与数组两种结构）。

    每个节点（dict / list / 标量）恰好回调一次；dict/list 继续下钻。
    """
    cb(path, None, obj)
    if isinstance(obj, dict):
        for k, v in obj.items():
            child = f"{path}.{k}"
            if isinstance(v, (dict, list)):
                _walk(v, child, cb)
            else:
                cb(child, k, v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            child = f"{path}[{i}]"
            if isinstance(v, (dict, list)):
                _walk(v, child, cb)
            else:
                cb(child, None, v)


def find_contact_violations(payload: Any, canary_values: list[str]) -> list[str]:
    """返回全部违规项（空列表 = 通过）。三重检查：禁键 / 金丝雀值 / 正则。"""
    canary_set = set(canary_values)
    violations: list[str] = []

    def cb(path: str, key: str | None, value: Any) -> None:
        # 键名精确匹配（避免误伤含子串的正常业务键）。
        # 标量节点带 key；容器节点从路径末段推导（覆盖「禁键的值为对象/数组」的形态）。
        nk = key if key is not None else path.rsplit(".", 1)[-1]
        if nk in BANNED_KEYS:
            violations.append(f"{path}: 禁键「{nk}」出现在响应中")
        if isinstance(value, str):
            if value in canary_set:
                violations.append(f"{path}: 金丝雀值泄露（值已脱敏显示）")
            if MOBILE_RE.search(value):
                violations.append(f"{path}: 字符串命中手机号正则")
            if EMAIL_RE.search(value):
                violations.append(f"{path}: 字符串命中邮箱正则")
            if LANDLINE_RE.search(value):
                violations.append(f"{path}: 字符串命中座机正则")

    _walk(payload, "$", cb)
    return violations


def assert_no_contact(payload: Any, canary_values: list[str]) -> None:
    """★ 可复用断言函数（本单交付物之一）。任何违规即 AssertionError。"""
    violations = find_contact_violations(payload, canary_values)
    if violations:
        # 不输出金丝雀原值，避免证据文件本身成为泄露源
        shown = [v.replace("金丝雀值泄露（值已脱敏显示）", "金丝雀值泄露") for v in violations]
        raise AssertionError(
            f"联系方式脱敏校验失败，共 {len(violations)} 处违规：\n" + "\n".join(shown)
        )


def _decimal_places(x: float | int) -> int:
    s = repr(float(x))
    if "e" in s or "E" in s:
        return 99
    return len(s.split(".")[1].rstrip("0")) if "." in s else 0


def find_coord_violations(payload: Any, street_centers: list[dict]) -> list[str]:
    """R2 坐标检查：lat/lng 必须成对出现、恰好等于某街道中心点、小数 ≤4 位。"""
    centers = {(c["lat"], c["lng"]) for c in street_centers}
    violations: list[str] = []

    def cb(path: str, key: str | None, value: Any) -> None:
        if isinstance(value, dict) and ("lat" in value or "lng" in value):
            if "lat" not in value or "lng" not in value:
                violations.append(f"{path}: 坐标对象缺少 lat 或 lng")
                return
            lat, lng = value["lat"], value["lng"]
            if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
                violations.append(f"{path}: lat/lng 不是数值")
                return
            if (lat, lng) not in centers:
                violations.append(
                    f"{path}: 坐标 ({lat}, {lng}) 不等于任何街道中心点"
                )
            dp = max(_decimal_places(lat), _decimal_places(lng))
            if dp > 4:
                violations.append(f"{path}: 坐标小数位数 {dp} 超过 4 位")

    _walk(payload, "$", cb)
    return violations


def assert_street_level_coord(payload: Any, street_centers: list[dict]) -> None:
    violations = find_coord_violations(payload, street_centers)
    if violations:
        raise AssertionError(
            f"街道级坐标校验失败，共 {len(violations)} 处违规：\n" + "\n".join(violations)
        )
