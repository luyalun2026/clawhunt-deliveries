# -*- coding: utf-8 -*-
"""公共夹具：被测入口统一走 HTTP（TestClient 或可配置 base URL），断言按受限原文与价格信号。"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import kb_api  # noqa: E402
from app.main import app  # noqa: E402

BASE_URL = os.environ.get("KB_BASE_URL")  # 设了就打真实服务，否则用进程内 TestClient


def _make_client():
    if BASE_URL:
        import httpx
        return httpx.Client(base_url=BASE_URL, timeout=10.0)
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture(scope="session")
def client():
    c = _make_client()
    yield c
    c.close()


@pytest.fixture(autouse=True)
def _fresh():
    kb_api.reset()
    yield


class KB:
    """薄封装：统一 header 与 JSON，避免测试直接触碰内部实现。"""

    def __init__(self, client):
        self.c = client

    def ask(self, user_id, question, session_id=None):
        body = {"question": question}
        if session_id:
            body["session_id"] = session_id
        return self.c.post("/api/kb/ask", json=body, headers={"X-User-Id": user_id})

    def slice(self, user_id, slice_id):
        return self.c.get("/api/kb/slices/%s" % slice_id, headers={"X-User-Id": user_id})

    def session(self, user_id, session_id):
        return self.c.get("/api/kb/sessions/%s" % session_id, headers={"X-User-Id": user_id})


@pytest.fixture()
def kb(client):
    return KB(client)


# ---- 泄露断言（单一来源：corpus.json 的受限文档） ----

RESTRICTED_TEXTS = kb_api.restricted_texts()
PRICE_SIGNALS = kb_api.restricted_price_signals()
RESTRICTED_SLICES = set(kb_api.restricted_slice_ids())
UNAUTHORIZED_USERS = ("u_member1", "u_member2", "u_recep1", "u_mgr1")


def _authorized_restricted(user_id):
    """该角色依法可见的受限切片（有权限引用时允许出现价格数字）。"""
    role = kb_api.USERS.get(user_id)
    if role is None:
        return set()
    return {sid for doc in kb_api.CORPUS
            if doc["status"] == "active" and doc.get("restricted") and role in doc["roles"]
            for sid in doc["slices"]}


def assert_no_leak(payload, user_id=None):
    """回答与引用中不得出现受限切片原文、价格数字/折扣串；引用不得越权。"""
    answer = payload.get("answer", "")
    citations = payload.get("citations", [])
    norm = answer.replace(" ", "")
    allowed = _authorized_restricted(user_id)
    if citations and set(citations) <= allowed:
        return  # 合法授权读取：允许出现价格数字
    for text in RESTRICTED_TEXTS:
        body = text.split("。")[0].replace(" ", "")
        assert body not in norm, "泄露受限原文: %r" % body
    for sig in PRICE_SIGNALS:
        assert sig.replace(" ", "") not in norm, "泄露价格信号: %r in %r" % (sig, answer)
    if user_id in UNAUTHORIZED_USERS:
        for sid in citations:
            assert sid not in RESTRICTED_SLICES, "越权引用受限切片: %s" % sid


def assert_refused(payload, user_id=None):
    assert payload["refused"] is True
    assert payload["answer"] == kb_api.REFUSAL
    assert payload["citations"] == []
    assert_no_leak(payload, user_id)
