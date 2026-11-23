# -*- coding: utf-8 -*-
"""把内存版 Api 暴露为真实 HTTP 服务（FastAPI），用于接口层与页面层越权验证。

设计要点
--------
1. 身份来自请求头 X-Actor（缺失 = 匿名），与真实网关的「已认证主体」等价；
   生产环境替换为 JWT 解析即可，业务判定逻辑完全复用 app/authz.py。
2. 六类越权在 HTTP 层返回 401/403/404，与内存实现一致。
3. 另提供两个服务端渲染页面（/leads、/leads/{id}），供 Playwright 走页面越权路径。
4. 全部虚构数据，不出现客户名称。

启动：uvicorn app.http_api:app --port 8137
"""
from __future__ import annotations

import csv
import io
from typing import Annotated

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from app.authz import ROLES, Api, seed

app = FastAPI(title="authz-2829", version="1.2.0")

# 单例被测系统：进程内共享，审计与线索状态连续
API: Api = seed()


def current_actor(x_actor: Annotated[str | None, Header()] = None):
    """把 X-Actor 请求头映射为主体；未知或缺失一律按匿名处理（默认拒绝）。"""
    if not x_actor:
        return ROLES["anonymous"]
    return ROLES.get(x_actor, ROLES["anonymous"])


ActorDep = Annotated[object, Depends(current_actor)]


def _json(code: int, body) -> Response:
    return JSONResponse(status_code=code, content=body)


# ---------------------------------------------------------------- 接口层
@app.get("/api/leads")
def list_leads(actor: ActorDep):
    code, body = API.list_leads(actor)               # type: ignore[arg-type]
    return _json(code, body)


@app.get("/api/leads/export")
def export_leads(actor: ActorDep, page: int = 1, size: int = 100):
    """导出为真实 CSV 文件（附件），行数即 A 可见线索条数。"""
    code, body = API.export_leads(actor, page, size)  # type: ignore[arg-type]
    if code != 200:
        return _json(code, body)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["id", "ent_name", "site_id", "owner_id"])
    writer.writeheader()
    for row in body["rows"]:
        writer.writerow({k: ("" if row.get(k) is None else row.get(k))
                         for k in writer.fieldnames})
    payload = "\ufeff" + buf.getvalue()          # BOM：Excel 直接打开不乱码
    return Response(
        content=payload.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=leads-export.csv",
                 "X-Export-Rows": str(len(body["rows"]))},
    )


@app.get("/api/search")
def search_leads(actor: ActorDep, q: str = ""):
    code, body = API.search(actor, q)                # type: ignore[arg-type]
    return _json(code, body)


@app.get("/api/leads/{lead_id}")
def get_lead(lead_id: str, actor: ActorDep):
    code, body = API.get_lead(actor, lead_id)        # type: ignore[arg-type]
    return _json(code, body)


@app.get("/api/leads/{lead_id}/quote")
def get_quote(lead_id: str, actor: ActorDep):
    code, body = API.get_quote(actor, lead_id)       # type: ignore[arg-type]
    return _json(code, body)


@app.get("/api/leads/{lead_id}/contract")
def get_contract(lead_id: str, actor: ActorDep):
    code, body = API.get_contract(actor, lead_id)    # type: ignore[arg-type]
    return _json(code, body)


@app.patch("/api/leads/{lead_id}/owner")
async def patch_owner(lead_id: str, request: Request, actor: ActorDep):
    payload = await request.json()
    code, body = API.change_owner(actor, lead_id, payload.get("owner_id"))  # type: ignore[arg-type]
    return _json(code, body)


@app.get("/api/audit/denied")
def audit_denied(_: ActorDep):
    rows = API.audit_denied()
    return _json(200, {"items": rows, "total": len(rows)})


# ---------------------------------------------------------------- 页面层（服务端渲染）
@app.get("/leads", response_class=HTMLResponse)
def page_leads(actor: ActorDep):
    code, body = API.list_leads(actor)               # type: ignore[arg-type]
    if code != 200:
        return HTMLResponse(status_code=code, content=_deny_page(code))
    rows = "".join(
        f'<li class="lead" data-id="{r["id"]}">{r["ent_name"]}'
        f'<a class="open" href="/leads/{r["id"]}">详情</a></li>'
        for r in body["items"]
    )
    html = (
        "<!doctype html><meta charset='utf-8'><title>线索</title>"
        f"<h1>线索列表</h1><p id='count'>{body['total']}</p>"
        f"<ul id='leads'>{rows}</ul>"
    )
    return HTMLResponse(status_code=200, content=html)


@app.get("/leads/{lead_id}", response_class=HTMLResponse)
def page_lead(lead_id: str, actor: ActorDep):
    code, body = API.get_lead(actor, lead_id)        # type: ignore[arg-type]
    if code != 200:
        return HTMLResponse(status_code=code, content=_deny_page(code))
    html = (
        "<!doctype html><meta charset='utf-8'><title>线索详情</title>"
        f"<h1 id='name'>{body['ent_name']}</h1>"
        f"<p id='owner'>{body['owner_id']}</p>"
    )
    return HTMLResponse(status_code=200, content=html)


@app.get("/search", response_class=HTMLResponse)
def page_search(actor: ActorDep, q: str = ""):
    code, body = API.search(actor, q)                # type: ignore[arg-type]
    if code != 200:
        return HTMLResponse(status_code=code, content=_deny_page(code))
    rows = "".join(
        f'<li class="lead" data-id="{r["id"]}">{r["ent_name"]}'
        f'<a class="open" href="/leads/{r["id"]}">详情</a></li>'
        for r in body["items"]
    )
    html = (
        "<!doctype html><meta charset='utf-8'><title>搜索线索</title>"
        "<h1>全局搜索</h1>"
        f"<p id='q'>{body['q']}</p><p id='count'>{body['total']}</p>"
        f"<ul id='results'>{rows}</ul>"
    )
    return HTMLResponse(status_code=200, content=html)


@app.get("/export", response_class=HTMLResponse)
def page_export(actor: ActorDep):
    code, body = API.export_leads(actor)             # type: ignore[arg-type]
    if code != 200:
        return HTMLResponse(status_code=code, content=_deny_page(code))
    html = (
        "<!doctype html><meta charset='utf-8'><title>导出线索</title>"
        "<h1>导出线索</h1>"
        f"<p id='rows'>{len(body['rows'])}</p>"
        "<a id='download' href='/api/leads/export' download>下载 CSV</a>"
    )
    return HTMLResponse(status_code=200, content=html)


def _deny_page(code: int) -> str:
    label = {401: "未登录", 403: "无权访问", 404: "未找到"}.get(code, "错误")
    return (
        "<!doctype html><meta charset='utf-8'><title>提示</title>"
        f"<h1 id='deny'>{label}</h1><p>该页面不可访问。</p>"
    )


@app.get("/healthz")
def healthz():
    return {"ok": True}
