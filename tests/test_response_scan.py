# -*- coding: utf-8 -*-
"""响应扫描（AC #1）：枚举全部 /api/mini/ GET 接口 × 4 种身份，逐响应递归脱敏检查。"""
from __future__ import annotations

import json

from app.assertions import assert_no_contact
from tests.scan_helper import CANARY, IDENTITIES, client, iter_requests, list_mini_get_endpoints  # noqa: F401


def test_scan_all_mini_get_endpoints_four_identities(client):
    eps = list_mini_get_endpoints(client)
    # OpenAPI 枚举必须覆盖全部会员端 GET 接口（当前 8 条；新增接口自动纳入）
    assert len(eps) >= 8, f"枚举到 {len(eps)} 条 /api/mini/ GET 接口，低于预期 8 条"

    scanned = 0
    auth_rejected = 0
    for ep in eps:
        for role, url, headers in iter_requests(client, ep):
            r = client.get(url, headers=headers)
            # 200 = 正常业务响应；401/403 = 身份校验拒绝（同样纳入扫描，拒绝体也必须干净）
            assert r.status_code in (200, 401, 403), \
                f"GET {url}（{role}）状态码 {r.status_code}: {r.text[:200]}"
            if r.status_code != 200:
                auth_rejected += 1
            payload = r.json()
            # 逐响应递归检查：金丝雀值 / 禁键 / 手机号·邮箱·座机正则
            assert_no_contact(payload, CANARY)
            scanned += 1

    # 记录扫描规模，供报告引用
    report = {
        "endpoints": [e["path"] for e in eps],
        "endpoint_count": len(eps),
        "identities": IDENTITIES,
        "request_count": scanned,
        "auth_rejected_count": auth_rejected,
    }
    print("\nSCAN-REPORT " + json.dumps(report, ensure_ascii=False))
    # guest/none 身份必须被鉴权接口拒绝（身份矩阵真实生效）
    assert auth_rejected > 0, "没有任何请求被 401/403 拒绝 → 身份矩阵未生效"


def test_banned_keys_never_appear_anywhere(client):
    """独立检查：全部响应中不存在名为 phone/mobile/tel/email/wechat/wx_id/contact 的键。"""
    from app.assertions import BANNED_KEYS

    banned_hits = []
    for ep in list_mini_get_endpoints(client):
        for role, url, headers in iter_requests(client, ep):
            payload = client.get(url, headers=headers).json()

            def walk(obj, path="$", key=None):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k in BANNED_KEYS:
                            banned_hits.append(f"{path}.{k}")
                        walk(v, f"{path}.{k}", k)
                elif isinstance(obj, list):
                    for i, v in enumerate(obj):
                        walk(v, f"{path}[{i}]", key)

            walk(payload)
    assert banned_hits == [], f"发现禁键：{banned_hits}"


def test_guest_and_unauthenticated_get_401_on_profile(client):
    """身份区分有效性：guest / none 调 profile 必须 401，member / admin 必须 200。"""
    assert client.get("/api/mini/profile").status_code == 401
    assert client.get("/api/mini/profile", headers={"X-Auth-Role": "none"}).status_code == 401
    assert client.get("/api/mini/profile", headers={"X-Auth-Role": "member"}).status_code == 200
    assert client.get("/api/mini/profile", headers={"X-Auth-Role": "admin"}).status_code == 200
