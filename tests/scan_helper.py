# -*- coding: utf-8 -*-
"""扫描辅助：从 OpenAPI 枚举 /api/mini/ 的 GET 接口并自动填充参数。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PKG_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PKG_ROOT))

from app.main import app  # noqa: E402
from app.seed import CANARY_COMPANIES, MAP_STREETS, NOTICES, all_canary_values  # noqa: E402

IDENTITIES = ["guest", "none", "member", "admin"]


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


def list_mini_get_endpoints(client: TestClient) -> list[dict]:
    """从 OpenAPI 文档枚举 /api/mini/ 下全部 GET 接口。

    返回 [{"path", "params": [路径参数名], "query": [查询参数名]}]
    """
    openapi = client.get("/openapi.json").json()
    eps = []
    for path, methods in sorted(openapi["paths"].items()):
        if "get" not in methods or not path.startswith("/api/mini/"):
            continue
        op = methods["get"]
        params = op.get("parameters") or []
        eps.append({
            "path": path,
            "params": [p["name"] for p in params if p.get("in") == "path"],
            "query": [p["name"] for p in params if p.get("in") == "query"],
        })
    return eps


# 与路径参数名对应的填充值（全部来自种子数据，使请求落在正常业务分支）
PATH_FILLERS = {
    "company_id": [c["id"] for c in CANARY_COMPANIES],
    "notice_id": [n["id"] for n in NOTICES],
    "street_id": [s["id"] for s in MAP_STREETS],
}

QUERY_FILLERS = {
    "lat": [30.5123, 30.5234],
    "lng": [114.3123, 114.3234],
}


def iter_requests(client: TestClient, ep: dict):
    """对每个接口生成全部 身份 × 路径填充 组合的请求。"""
    from itertools import product

    path_variants = [ep["path"]]
    for pname in ep["params"]:
        fillers = PATH_FILLERS.get(pname, ["cm-0001"])
        path_variants = [
            pv.replace("{" + pname + "}", f)
            for pv in path_variants for f in fillers
        ]
    for pv, role in product(path_variants, IDENTITIES):
        qs = ""
        if ep["query"]:
            parts = []
            for qname in ep["query"]:
                v = QUERY_FILLERS.get(qname, [30.5123])[0]
                parts.append(f"{qname}={v}")
            qs = "?" + "&".join(parts)
        url = pv + qs
        headers = {} if role == "guest" else {"X-Auth-Role": role}
        yield role, url, headers


CANARY = all_canary_values()
