# -*- coding: utf-8 -*-
"""FastAPI 应用：知识库问答对外 HTTP 接口（统一技术约定：Python 3.11+ / FastAPI）。

路由（与 ROUTES 一致，OpenAPI 可枚举）：
  POST /api/kb/ask                      {"question": str, "session_id": str|null}
  GET  /api/kb/slices/{slice_id}
  GET  /api/kb/sessions/{session_id}

鉴权：请求头 X-User-Id（缺省 → 401 unauthorized）。
无权限 / 不存在 / 已下线 / 已删除 → 四种情形返回**完全相同**的 404 响应体。
与 S2-IAM 对接点：把 X-User-Id 换成 IAM 下发的 subject 并注入 role 声明即可，
其余判定逻辑无需改动（见 README「对接点」）。
"""
from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from . import kb_api

app = FastAPI(title="KB QA (adversarial stub)", version="2.0.0")

ROUTES = [
    ("POST", "/api/kb/ask"),
    ("GET", "/api/kb/slices/{slice_id}"),
    ("GET", "/api/kb/sessions/{session_id}"),
]


def _unauthorized() -> JSONResponse:
    return JSONResponse(kb_api.UNAUTHORIZED_BODY, status_code=401)


def _not_found() -> JSONResponse:
    # 四种情形共用同一响应体与状态码
    return JSONResponse(kb_api.NOT_FOUND_BODY, status_code=404)


def _role(x_user_id: str | None) -> str | None:
    if not x_user_id:
        return None
    try:
        return kb_api.role_of(x_user_id)
    except KeyError:
        return None


@app.post("/api/kb/ask")
async def ask(request: Request, x_user_id: str | None = Header(default=None)):
    if _role(x_user_id) is None:
        return _unauthorized()
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="invalid json")
    question = (body or {}).get("question")
    if not isinstance(question, str) or not question.strip():
        raise HTTPException(status_code=422, detail="question required")
    out = kb_api.ask(x_user_id, question, (body or {}).get("session_id"))
    return out


@app.get("/api/kb/slices/{slice_id}")
async def slice_detail(slice_id: str, x_user_id: str | None = Header(default=None)):
    if _role(x_user_id) is None:
        return _unauthorized()
    try:
        return kb_api.get_slice(x_user_id, slice_id)
    except KeyError:
        return _not_found()


@app.get("/api/kb/sessions/{session_id}")
async def session_detail(session_id: str, x_user_id: str | None = Header(default=None)):
    if _role(x_user_id) is None:
        return _unauthorized()
    return kb_api.session_state(session_id)
