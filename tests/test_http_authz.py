# -*- coding: utf-8 -*-
"""接口层越权验证：真实启动 uvicorn，用 httpx 发请求断言状态码。

针对返工意见二：此前只在内存对象上断言，本文件补齐「可启动的 HTTP 服务 + httpx」证据。
六类越权路径逐一覆盖，并核对审计条数 == 越权尝试次数（AC4）。
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def base_url():
    port = _free_port()
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.http_api:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=str(ROOT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30
    ok = False
    while time.time() < deadline:
        if proc.poll() is not None:
            out = proc.stdout.read().decode("utf-8", "replace") if proc.stdout else ""
            raise RuntimeError(f"uvicorn 提前退出：\n{out}")
        try:
            if httpx.get(url + "/healthz", timeout=1.0).status_code == 200:
                ok = True
                break
        except Exception:
            time.sleep(0.2)
    if not ok:
        proc.kill()
        raise RuntimeError("uvicorn 未在 30s 内就绪")
    yield url
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def H(actor: str | None):
    return {} if actor is None else {"X-Actor": actor}


# --------------------------------------------------------------- AC1 / AC3
def test_ac1_list_returns_exactly_8(base_url):
    """A 的线索列表恰好 8 条：本人 5 + 公海 3。"""
    r = httpx.get(base_url + "/api/leads", headers=H("A"), timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 8
    ids = {row["id"] for row in body["items"]}
    assert ids == {f"L-A{i}" for i in range(1, 6)} | {f"L-P{i}" for i in range(1, 4)}


def test_ac3_export_row_count_is_8(base_url):
    """导出必须是真实文件（CSV 附件），读回后数据行恰为 8，且只含 A 的 5 条 + 公海 3 条。"""
    import csv
    import io as _io

    r = httpx.get(base_url + "/api/leads/export", headers=H("A"), timeout=10)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers.get("content-disposition", "")
    assert r.headers.get("x-export-rows") == "8"

    rows = list(csv.DictReader(_io.StringIO(r.text.lstrip("\ufeff"))))
    assert len(rows) == 8, rows
    ids = {row["id"] for row in rows}
    assert ids == {f"L-A{i}" for i in range(1, 6)} | {f"L-P{i}" for i in range(1, 4)}
    assert not any(i.startswith("L-B") or i.startswith("L-OTHER") or i == "L-DEL" for i in ids)
    assert "虚构乙企业" not in r.text
    # 文件行数（含表头）= 1 + 8
    assert len([ln for ln in r.text.strip().splitlines() if ln.strip()]) == 9


def test_ac2_search_does_not_return_other_tenant(base_url):
    """A 全局搜索 B 的企业名：接口不返回 B 的任何线索。"""
    r = httpx.get(base_url + "/api/search", params={"q": "虚构乙企业"}, headers=H("A"), timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["items"] == []
    assert all(not row["id"].startswith("L-B") for row in r.json().get("items", []))
    assert "虚构乙企业1" not in r.text   # 查询词回显允许，但不得回显对方任何线索内容


def test_ac2_search_returns_only_in_scope(base_url):
    """A 搜索「虚构」：只返回 A 可见的 8 条，不含 B 的编号。"""
    r = httpx.get(base_url + "/api/search", params={"q": "虚构"}, headers=H("A"), timeout=10)
    body = r.json()
    assert r.status_code == 200
    assert body["total"] == 8
    assert all(not row["id"].startswith("L-B") for row in body["items"])


# --------------------------------------------------------------- AC2 六类越权
DENY_CASES = [
    # (说明, method, path, headers, body, 期望状态码)
    ("读他人线索详情", "GET", "/api/leads/L-B1", H("A"), None, 404),
    ("读他人报价", "GET", "/api/leads/L-B2/quote", H("A"), None, 404),
    ("读他人合同", "GET", "/api/leads/L-B3/contract", H("A"), None, 404),
    ("改他人归属", "PATCH", "/api/leads/L-B4/owner", H("A"), {"owner_id": "consultant-a"}, 403),
    ("匿名读列表", "GET", "/api/leads", H(None), None, 401),
    ("读他站线索", "GET", "/api/leads/L-OTHER-SITE", H("A"), None, 404),
    ("读软删除线索", "GET", "/api/leads/L-DEL", H("A"), None, 404),
    ("未知主体读列表", "GET", "/api/leads", H("not-exist"), None, 401),
    ("匿名导出线索", "GET", "/api/leads/export", H(None), None, 401),
    ("匿名全局搜索", "GET", "/api/search?q=x", H(None), None, 401),
]


@pytest.mark.parametrize("desc,method,path,headers,body,want", DENY_CASES,
                         ids=[c[0] for c in DENY_CASES])
def test_ac2_denied_over_http(base_url, desc, method, path, headers, body, want):
    r = httpx.request(method, base_url + path, headers=headers, json=body, timeout=10)
    assert r.status_code == want, f"{desc}: 期望 {want}，实际 {r.status_code} {r.text}"


def test_ac2_forbidden_body_does_not_leak(base_url):
    """404 响应体不得出现企业名，避免通过错误信息泄露存在性。"""
    r = httpx.get(base_url + "/api/leads/L-B1", headers=H("A"), timeout=10)
    assert r.status_code == 404
    assert "虚构乙企业" not in r.text
    assert r.json() == {"error": "not_found"}


def test_ac2_owner_unchanged_after_forbidden_patch(base_url):
    """越权 PATCH 被拒后，B 的线索归属未被改动。"""
    httpx.patch(base_url + "/api/leads/L-B4/owner", headers=H("A"),
                json={"owner_id": "consultant-a"}, timeout=10)
    r = httpx.get(base_url + "/api/leads/L-B4", headers=H("B"), timeout=10)
    assert r.status_code == 200
    assert r.json()["owner_id"] == "consultant-b"


# --------------------------------------------------------------- AC4 审计对拍
def test_ac4_audit_rows_equal_denied_attempts(base_url):
    """审计条数 == 越权尝试次数：独立进程内先取基线，再打 N 次，增量必须等于 N。"""
    before = httpx.get(base_url + "/api/audit/denied", headers=H("A"), timeout=10).json()["total"]
    attempts = [
        ("GET", "/api/leads/L-B1", None),
        ("GET", "/api/leads/L-B2/quote", None),
        ("GET", "/api/leads/L-B3/contract", None),
        ("PATCH", "/api/leads/L-B5/owner", {"owner_id": "consultant-a"}),
        ("GET", "/api/leads/L-OTHER-SITE", None),
        ("GET", "/api/leads/L-DEL", None),
    ]
    for method, path, payload in attempts:
        httpx.request(method, base_url + path, headers=H("A"), json=payload, timeout=10)
    after = httpx.get(base_url + "/api/audit/denied", headers=H("A"), timeout=10).json()
    assert after["total"] - before == len(attempts)
    tail = after["items"][-len(attempts):]
    assert all(row["result"] == "denied" and row["actor_id"] == "consultant-a" for row in tail)


# --------------------------------------------------------------- 页面层（服务端渲染）
PAGE_CASES = [
    ("A 直接访问 B 的线索页", "/leads/L-B1", H("A"), 404, "未找到"),
    ("匿名访问线索列表页", "/leads", H(None), 401, "未登录"),
    ("A 访问他站线索页", "/leads/L-OTHER-SITE", H("A"), 404, "未找到"),
    ("A 打开 B 线索详情直达 URL（页面）", "/leads/L-B2", H("A"), 404, "未找到"),
    ("匿名打开导出页", "/export", H(None), 401, "未登录"),
    ("匿名打开搜索页", "/search?q=x", H(None), 401, "未登录"),
]


@pytest.mark.parametrize("desc,path,headers,want,label", PAGE_CASES,
                         ids=[c[0] for c in PAGE_CASES])
def test_page_layer_denied(base_url, desc, path, headers, want, label):
    r = httpx.get(base_url + path, headers=headers, timeout=10)
    assert r.status_code == want, desc
    assert label in r.text


def test_page_layer_allowed(base_url):
    r = httpx.get(base_url + "/leads", headers=H("A"), timeout=10)
    assert r.status_code == 200
    assert "id='count'>8<" in r.text


def test_page_link_click_equivalent(base_url):
    """等价于页面点击：从列表页解析每条线索的 href，逐个请求，断言仅本人/公海可达且详情正确。"""
    import re as _re

    r = httpx.get(base_url + "/leads", headers=H("A"), timeout=10)
    assert r.status_code == 200
    hrefs = _re.findall(r'<a class="open" href="([^"]+)"', r.text)
    assert len(hrefs) == 8, hrefs
    assert all(h.startswith("/leads/L-") for h in hrefs)
    for h in hrefs:
        d = httpx.get(base_url + h, headers=H("A"), timeout=10)
        assert d.status_code == 200, h
        assert "id='name'" in d.text
    # 列表页出现的 8 个 id 与详情页可达集合完全一致，无越界链接
    ids = set(_re.findall(r'data-id="([^"]+)"', r.text))
    assert ids == {h.rsplit("/", 1)[-1] for h in hrefs}


def test_page_denied_hides_other_tenant_name(base_url):
    """他人线索页 404 且响应体不含对方企业名（页面层不泄露）。"""
    r = httpx.get(base_url + "/leads/L-B1", headers=H("A"), timeout=10)
    assert r.status_code == 404
    assert "虚构乙企业" not in r.text
    assert "未找到" in r.text


def test_page_search_does_not_show_other_tenant(base_url):
    """页面层：A 搜索 B 的企业名，结果页计数 0 且不含对方企业名。"""
    r = httpx.get(base_url + "/search", params={"q": "虚构乙企业"}, headers=H("A"), timeout=10)
    assert r.status_code == 200
    assert "id='count'>0<" in r.text
    assert "虚构乙企业1" not in r.text
    assert "data-id='L-B" not in r.text
    assert "id='results'>" in r.text


def test_page_export_shows_8_rows_and_download_link(base_url):
    """页面层：导出页显示 8 行并提供真实文件下载链接。"""
    r = httpx.get(base_url + "/export", headers=H("A"), timeout=10)
    assert r.status_code == 200
    assert "id='rows'>8<" in r.text
    assert "href='/api/leads/export'" in r.text


def test_ac4_anonymous_search_and_export_are_audited(base_url):
    """审计口径：导出/搜索两类的匿名访问计入越权尝试并写 access_denied。"""
    before = httpx.get(base_url + "/api/audit/denied", headers=H("A"), timeout=10).json()["total"]
    httpx.get(base_url + "/api/leads/export", timeout=10)
    httpx.get(base_url + "/api/search", params={"q": "x"}, timeout=10)
    after = httpx.get(base_url + "/api/audit/denied", headers=H("A"), timeout=10).json()
    assert after["total"] - before == 2
    kinds = {row["resource_type"] for row in after["items"][-2:]}
    assert kinds == {"export", "search"}
