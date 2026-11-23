# -*- coding: utf-8 -*-
"""页面层越权验证：Playwright 真实浏览器走一遍越权路径。

针对返工意见二「用 A 的身份分别通过页面和接口访问」中的页面一半。
启动独立 uvicorn 进程，浏览器携带 X-Actor=A 访问，断言：
  - 列表页渲染 8 条，可直接点进本人线索；
  - 直接输入他人线索 URL 时页面显示「未找到」，且不出现对方企业名；
  - 匿名访问列表页显示「未登录」。

运行前置：`playwright install chromium`（或本机已有 chromium / msedge）。
无 Playwright 时本文件整体跳过，不影响其余测试。
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

sync_api = pytest.importorskip("playwright.sync_api", reason="playwright 未安装")
sync_playwright = sync_api.sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server():
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
    while time.time() < deadline:
        if proc.poll() is not None:
            out = proc.stdout.read().decode("utf-8", "replace") if proc.stdout else ""
            raise RuntimeError(f"uvicorn 提前退出：\n{out}")
        try:
            if httpx.get(url + "/healthz", timeout=1.0).status_code == 200:
                break
        except Exception:
            time.sleep(0.2)
    else:
        proc.kill()
        raise RuntimeError("uvicorn 未在 30s 内就绪")
    yield url
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as pw:
        try:
            b = pw.chromium.launch(headless=True)
        except Exception:
            # 浏览器二进制与包版本不匹配时，退回本机已装 Edge
            b = pw.chromium.launch(headless=True, channel="msedge")
        yield b
        b.close()


@pytest.fixture()
def page_as(browser):
    def _make(actor: str | None):
        ctx = browser.new_context()
        if actor:
            ctx.set_extra_http_headers({"X-Actor": actor})
        return ctx.new_page()
    made = []

    def factory(actor):
        pg = _make(actor)
        made.append(pg)
        return pg
    yield factory
    for pg in made:
        pg.context.close()


def test_page_list_shows_8_leads(server, page_as):
    pg = page_as("A")
    pg.goto(server + "/leads", wait_until="load")
    assert pg.inner_text("#count").strip() == "8"
    assert pg.locator("li.lead").count() == 8
    assert "虚构乙企业" not in pg.content()


def test_page_click_through_own_lead(server, page_as):
    pg = page_as("A")
    pg.goto(server + "/leads", wait_until="load")
    pg.locator("li.lead[data-id='L-A1'] a.open").click()
    pg.wait_for_load_state("load")
    assert pg.inner_text("#name").strip() == "虚构甲企业1"


def test_page_other_lead_denied(server, page_as):
    pg = page_as("A")
    resp = pg.goto(server + "/leads/L-B1", wait_until="load")
    assert resp.status == 404
    assert pg.inner_text("#deny").strip() == "未找到"
    assert "虚构乙企业" not in pg.content()


def test_page_anonymous_denied(server, page_as):
    pg = page_as(None)
    resp = pg.goto(server + "/leads", wait_until="load")
    assert resp.status == 401
    assert pg.inner_text("#deny").strip() == "未登录"


def test_page_search_does_not_return_other_tenant(server, page_as):
    """页面层：以 A 身份全局搜索 B 的企业名，结果 0 条、不出现对方任何线索。"""
    pg = page_as("A")
    resp = pg.goto(server + "/search?q=%E8%99%9A%E6%9E%84%E4%B9%99%E4%BC%81%E4%B8%9A", wait_until="load")
    assert resp.status == 200
    assert pg.inner_text("#count").strip() == "0"
    assert pg.locator("li.lead").count() == 0
    assert "虚构乙企业1" not in pg.content()


def test_page_search_returns_own_scope(server, page_as):
    """页面层：A 搜索「虚构」返回 8 条，全部为本人/公海。"""
    pg = page_as("A")
    pg.goto(server + "/search?q=%E8%99%9A%E6%9E%84", wait_until="load")
    assert pg.inner_text("#count").strip() == "8"
    assert pg.locator("li.lead").count() == 8
    ids = pg.eval_on_selector_all("li.lead", "els => els.map(e => e.dataset.id)")
    assert all(not i.startswith("L-B") for i in ids)


def test_page_export_downloads_csv_with_8_rows(server, page_as):
    """页面层：导出页显示 8 行，并给出真实 CSV 文件链接；用页面所在浏览器上下文取回文件核对。

    说明：Edge headless 在本环境会把 download 事件标记为 canceled，故用
    `page.context.request`（同一浏览器上下文、携带同一 X-Actor）读取文件本体，
    既验证了链接指向真实文件，也避免依赖浏览器的下载落盘行为。
    """
    pg = page_as("A")
    resp = pg.goto(server + "/export", wait_until="load")
    assert resp.status == 200
    assert pg.inner_text("#rows").strip() == "8"
    href = pg.get_attribute("#download", "href")
    assert href == "/api/leads/export"
    file_resp = pg.context.request.get(server + href)
    assert file_resp.status == 200
    assert file_resp.headers.get("content-type", "").startswith("text/csv")
    text = file_resp.text().lstrip("﻿")
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    assert len(lines) == 9            # 表头 + 8 行数据
    assert "L-B" not in text
    assert "虚构乙企业" not in text


def test_page_export_anonymous_denied(server, page_as):
    pg = page_as(None)
    resp = pg.goto(server + "/export", wait_until="load")
    assert resp.status == 401
    assert pg.inner_text("#deny").strip() == "未登录"


def test_page_search_anonymous_denied(server, page_as):
    pg = page_as(None)
    resp = pg.goto(server + "/search?q=x", wait_until="load")
    assert resp.status == 401
    assert pg.inner_text("#deny").strip() == "未登录"
