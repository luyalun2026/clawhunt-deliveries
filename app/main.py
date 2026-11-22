# -*- coding: utf-8 -*-
"""招商模块（S3-SALES-056）FastAPI 被测服务。

统一约定：Python 3.11+ / FastAPI / 金额以分为整数 / 密钥只从环境变量读取 /
依赖 S2-IAM 的部分以 X-Actor-Id 头作为接口桩（见 app/security.py）。
路由全部挂在 /api/sales/ 下，供 OpenAPI 自动枚举与覆盖门禁使用。
"""
import json
import math
import re

from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app import clock, money
from app.security import current_actor, esign_secret, verify_signature
from app.store import can_view, can_write, new_db, visible_list

router = APIRouter(prefix="/api/sales", tags=["sales"])

PRESIGN_TTL_SECONDS = 300
_MASK_PHONE = re.compile(r"(?<!\d)\d{11}(?!\d)")


# ---------------------------------------------------------------- helpers
def _db(request):
    return request.app.state.db


def _load(request, actor, coll, item_id):
    """取对象；不存在或不可见统一 404（避免通过状态码探测他人对象是否存在）。"""
    obj = _db(request)[coll].get(item_id)
    if obj is None or not can_view(actor, obj):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
    return obj


def _load_writable(request, actor, coll, item_id):
    obj = _load(request, actor, coll, item_id)
    if not can_write(actor, obj):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
    return obj


def _patch(obj, body, allowed):
    for k, v in (body or {}).items():
        if k in allowed:
            obj[k] = v
    obj["updated_at"] = clock.now().isoformat()


def mask_phone(phone):
    if not isinstance(phone, str) or len(phone) < 7:
        return "***"
    return phone[:3] + "****" + phone[-4:]


def presign_token(attachment_id, expires_at):
    from app.security import sign_payload
    return sign_payload(_presign_secret(), {"aid": attachment_id, "exp": int(expires_at)})


def _presign_secret():
    import os
    secret = os.environ.get("PRESIGN_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail={"code": "PRESIGN_SECRET_MISSING"})
    return secret


# ---------------------------------------------------------------- leads
@router.get("/leads")
def list_leads(request: Request, actor=Depends(current_actor)):
    return {"items": visible_list(actor, _db(request)["leads"].values())}


@router.get("/leads/{lead_id}")
def get_lead(lead_id: str, request: Request, actor=Depends(current_actor)):
    return _load(request, actor, "leads", lead_id)


@router.put("/leads/{lead_id}")
def put_lead(lead_id: str, request: Request, body: dict = Body(default={}),
             actor=Depends(current_actor)):
    obj = _load_writable(request, actor, "leads", lead_id)
    _patch(obj, body, {"name", "company", "phone", "status", "source"})
    return obj


@router.patch("/leads/{lead_id}")
def patch_lead(lead_id: str, request: Request, body: dict = Body(default={}),
               actor=Depends(current_actor)):
    obj = _load_writable(request, actor, "leads", lead_id)
    _patch(obj, body, {"name", "company", "phone", "status", "source"})
    return obj


@router.post("/leads/{lead_id}/assign")
def assign_lead(lead_id: str, request: Request, body: dict = Body(default={}),
                actor=Depends(current_actor)):
    obj = _load(request, actor, "leads", lead_id)
    if actor["role"] != "supervisor" or obj["site_id"] != actor["site_id"]:
        raise HTTPException(status_code=403, detail={"code": "ASSIGN_FORBIDDEN"})
    target = _db(request)["users"].get(body.get("owner_id"))
    if not target or target["org_id"] != actor["org_id"] or target["site_id"] != actor["site_id"]:
        raise HTTPException(status_code=422, detail={"code": "INVALID_OWNER"})
    obj["owner_id"] = target["id"]
    obj["updated_at"] = clock.now().isoformat()
    return obj


# ---------------------------------------------------------------- followups
@router.get("/followups")
def list_followups(request: Request, actor=Depends(current_actor)):
    return {"items": visible_list(actor, _db(request)["followups"].values())}


@router.get("/followups/{item_id}")
def get_followup(item_id: str, request: Request, actor=Depends(current_actor)):
    return _load(request, actor, "followups", item_id)


@router.post("/followups")
def create_followup(request: Request, body: dict = Body(default={}),
                    actor=Depends(current_actor)):
    lead = _load(request, actor, "leads", body.get("lead_id"))
    if not can_write(actor, lead):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
    db = _db(request)
    fid = "fu-%d" % (len(db["followups"]) + 1)
    obj = {"id": fid, "org_id": actor["org_id"], "site_id": actor["site_id"],
           "owner_id": actor["id"], "created_by": actor["id"], "lead_id": lead["id"],
           "channel": body.get("channel", "电话"), "note": body.get("note", ""),
           "updated_at": clock.now().isoformat()}
    db["followups"][fid] = obj
    return obj


@router.put("/followups/{item_id}")
def put_followup(item_id: str, request: Request, body: dict = Body(default={}),
                 actor=Depends(current_actor)):
    obj = _load_writable(request, actor, "followups", item_id)
    _patch(obj, body, {"channel", "note"})
    return obj


@router.patch("/followups/{item_id}")
def patch_followup(item_id: str, request: Request, body: dict = Body(default={}),
                   actor=Depends(current_actor)):
    obj = _load_writable(request, actor, "followups", item_id)
    _patch(obj, body, {"channel", "note"})
    return obj


# ---------------------------------------------------------------- visits
@router.get("/visits")
def list_visits(request: Request, actor=Depends(current_actor)):
    return {"items": visible_list(actor, _db(request)["visits"].values())}


@router.get("/visits/{item_id}")
def get_visit(item_id: str, request: Request, actor=Depends(current_actor)):
    return _load(request, actor, "visits", item_id)


@router.post("/visits")
def create_visit(request: Request, body: dict = Body(default={}),
                 actor=Depends(current_actor)):
    lead = _load(request, actor, "leads", body.get("lead_id"))
    if not can_write(actor, lead):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
    db = _db(request)
    vid = "visit-%d" % (len(db["visits"]) + 1)
    obj = {"id": vid, "org_id": actor["org_id"], "site_id": actor["site_id"],
           "owner_id": actor["id"], "created_by": actor["id"], "lead_id": lead["id"],
           "visit_at": body.get("visit_at", ""), "status": "planned",
           "updated_at": clock.now().isoformat()}
    db["visits"][vid] = obj
    return obj


@router.put("/visits/{item_id}")
def put_visit(item_id: str, request: Request, body: dict = Body(default={}),
              actor=Depends(current_actor)):
    obj = _load_writable(request, actor, "visits", item_id)
    _patch(obj, body, {"visit_at", "status"})
    return obj


@router.patch("/visits/{item_id}")
def patch_visit(item_id: str, request: Request, body: dict = Body(default={}),
                actor=Depends(current_actor)):
    obj = _load_writable(request, actor, "visits", item_id)
    _patch(obj, body, {"visit_at", "status"})
    return obj


# ---------------------------------------------------------------- quotes
@router.get("/quotes")
def list_quotes(request: Request, actor=Depends(current_actor)):
    return {"items": visible_list(actor, _db(request)["quotes"].values())}


@router.get("/quotes/{item_id}")
def get_quote(item_id: str, request: Request, actor=Depends(current_actor)):
    return _load(request, actor, "quotes", item_id)


@router.post("/quotes")
def create_quote(request: Request, body: dict = Body(default={}),
                 actor=Depends(current_actor)):
    lead = _load(request, actor, "leads", body.get("lead_id"))
    if not can_write(actor, lead):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
    try:
        amounts = money.compute_amounts(body.get("unit_type", "office"),
                                        int(body.get("requested_concession_bps", 0)),
                                        int(body.get("lease_months", 12)))
    except money.RuleError as exc:
        raise HTTPException(status_code=422, detail={"code": "RULE_ERROR", "message": str(exc)})
    db = _db(request)
    qid = "quote-%d" % (len(db["quotes"]) + 1)
    obj = {"id": qid, "org_id": actor["org_id"], "site_id": actor["site_id"],
           "owner_id": actor["id"], "created_by": actor["id"], "lead_id": lead["id"],
           "unit_type": amounts["unit_type"], "lease_months": amounts["lease_months"],
           "concession_bps": amounts["concession_bps"], "status": "draft",
           "approval_steps": [{"role": "supervisor", "status": "pending", "decided_by": None},
                              {"role": "finance", "status": "pending", "decided_by": None}],
           "current_step": 0,
           "final_monthly_cents": amounts["final_monthly_cents"],
           "deposit_cents": amounts["deposit_cents"],
           "contract_total_cents": amounts["contract_total_cents"],
           "first_year_amount_cents": amounts["first_year_amount_cents"],
           "updated_at": clock.now().isoformat()}
    db["quotes"][qid] = obj
    return obj


@router.put("/quotes/{item_id}")
def put_quote(item_id: str, request: Request, body: dict = Body(default={}),
              actor=Depends(current_actor)):
    obj = _load_writable(request, actor, "quotes", item_id)
    if obj["status"] != "draft":
        raise HTTPException(status_code=409, detail={"code": "LOCKED_STATUS"})
    try:
        amounts = money.compute_amounts(body.get("unit_type", obj["unit_type"]),
                                        int(body.get("requested_concession_bps", obj["concession_bps"])),
                                        int(body.get("lease_months", obj["lease_months"])))
    except money.RuleError as exc:
        raise HTTPException(status_code=422, detail={"code": "RULE_ERROR", "message": str(exc)})
    obj.update({k: amounts[k] for k in ("unit_type", "lease_months", "concession_bps",
                                        "final_monthly_cents", "deposit_cents",
                                        "contract_total_cents", "first_year_amount_cents")})
    obj["updated_at"] = clock.now().isoformat()
    return obj


@router.patch("/quotes/{item_id}")
def patch_quote(item_id: str, request: Request, body: dict = Body(default={}),
                actor=Depends(current_actor)):
    return put_quote(item_id, request, body, actor)


@router.post("/quotes/{item_id}/submit")
def submit_quote(item_id: str, request: Request, actor=Depends(current_actor)):
    obj = _load(request, actor, "quotes", item_id)
    if obj["created_by"] != actor["id"]:
        raise HTTPException(status_code=403, detail={"code": "SUBMIT_FORBIDDEN"})
    if obj["status"] != "draft":
        raise HTTPException(status_code=409, detail={"code": "LOCKED_STATUS"})
    obj["status"] = "pending_approval"
    obj["updated_at"] = clock.now().isoformat()
    return obj


@router.post("/quotes/{item_id}/approve")
def approve_quote(item_id: str, request: Request, body: dict = Body(default={}),
                  actor=Depends(current_actor)):
    obj = _load(request, actor, "quotes", item_id)
    if obj["created_by"] == actor["id"]:
        raise HTTPException(status_code=403, detail={"code": "SELF_APPROVAL"})
    step = body.get("step")
    if not isinstance(step, int):
        raise HTTPException(status_code=422, detail={"code": "INVALID_STEP"})
    if step != obj["current_step"]:
        raise HTTPException(status_code=403, detail={"code": "STEP_ORDER"})
    expected_role = obj["approval_steps"][step]["role"]
    if actor["role"] != expected_role:
        raise HTTPException(status_code=403, detail={"code": "ROLE_MISMATCH"})
    obj["approval_steps"][step]["status"] = "approved"
    obj["approval_steps"][step]["decided_by"] = actor["id"]
    obj["current_step"] = step + 1
    if obj["current_step"] >= len(obj["approval_steps"]):
        obj["status"] = "approved"
    obj["updated_at"] = clock.now().isoformat()
    return obj


# ---------------------------------------------------------------- contracts
@router.get("/contracts")
def list_contracts(request: Request, actor=Depends(current_actor)):
    return {"items": visible_list(actor, _db(request)["contracts"].values())}


@router.get("/contracts/{item_id}")
def get_contract(item_id: str, request: Request, actor=Depends(current_actor)):
    return _load(request, actor, "contracts", item_id)


@router.patch("/contracts/{item_id}")
def patch_contract(item_id: str, request: Request, body: dict = Body(default={}),
                   actor=Depends(current_actor)):
    obj = _load_writable(request, actor, "contracts", item_id)
    if obj["status"] != "draft":
        raise HTTPException(status_code=409, detail={"code": "LOCKED_STATUS"})
    _patch(obj, body, {"note"})
    return obj


@router.post("/contracts/{item_id}/sign")
def sign_contract(item_id: str, request: Request, body: dict = Body(default={}),
                  actor=Depends(current_actor)):
    obj = _load_writable(request, actor, "contracts", item_id)
    if obj["status"] != "draft":
        raise HTTPException(status_code=409, detail={"code": "LOCKED_STATUS"})
    obj["status"] = "signed"
    obj["signed_at"] = clock.now().isoformat()
    obj["signer"] = body.get("signer_name", actor["name"])
    return obj


# ---------------------------------------------------------------- attachments
@router.get("/attachments")
def list_attachments(request: Request, actor=Depends(current_actor)):
    return {"items": visible_list(actor, _db(request)["attachments"].values())}


@router.post("/attachments/presign")
def presign_attachment(request: Request, body: dict = Body(default={}),
                       actor=Depends(current_actor)):
    att = _load(request, actor, "attachments", body.get("attachment_id"))
    exp = math.ceil(clock.now_ts()) + PRESIGN_TTL_SECONDS   # 向上取整，保证 TTL 不少于 300s
    token = presign_token(att["id"], exp)
    return {"url": "/api/sales/attachments/download?attachment_id=%s&exp=%d&token=%s"
                   % (att["id"], int(exp), token),
            "expires_in": PRESIGN_TTL_SECONDS,
            "expires_at": int(exp)}


@router.get("/attachments/download")
def download_attachment(request: Request, attachment_id: str = Query(...),
                        exp: int = Query(...), token: str = Query(...),
                        actor=Depends(current_actor)):
    """预签名链接的 TTL 校验就在这条路由上——返回的链接本身就是被校验对象。"""
    if clock.now_ts() > exp:
        raise HTTPException(status_code=410, detail={"code": "PRESIGN_EXPIRED"})
    if presign_token(attachment_id, exp) != token:
        raise HTTPException(status_code=403, detail={"code": "PRESIGN_INVALID"})
    att = _load(request, actor, "attachments", attachment_id)
    return {"attachment_id": att["id"], "filename": att["filename"],
            "content_type": att["content_type"], "size_bytes": att["size_bytes"],
            "download_url": "https://files.invalid/%s" % att["filename"]}


@router.get("/attachments/{item_id}")
def get_attachment(item_id: str, request: Request, actor=Depends(current_actor)):
    return _load(request, actor, "attachments", item_id)


@router.post("/attachments")
def create_attachment(request: Request, body: dict = Body(default={}),
                      actor=Depends(current_actor)):
    quote = _load(request, actor, "quotes", body.get("quote_id"))
    if not can_write(actor, quote):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
    db = _db(request)
    aid = "att-%d" % (len(db["attachments"]) + 1)
    obj = {"id": aid, "org_id": actor["org_id"], "site_id": actor["site_id"],
           "owner_id": actor["id"], "created_by": actor["id"], "quote_id": quote["id"],
           "filename": body.get("filename", "unnamed.pdf"),
           "content_type": body.get("content_type", "application/pdf"),
           "size_bytes": int(body.get("size_bytes", 0)),
           "updated_at": clock.now().isoformat()}
    db["attachments"][aid] = obj
    return obj


# ---------------------------------------------------------------- public pool
@router.get("/public-pool")
def public_pool(request: Request, actor=Depends(current_actor)):
    """公海线索只返回最少必要字段，手机号一律脱敏。"""
    items = []
    for lead in _db(request)["leads"].values():
        if lead.get("status") != "public" or lead.get("org_id") != actor["org_id"]:
            continue
        items.append({"id": lead["id"], "name": lead["name"], "company": lead["company"],
                      "site_id": lead["site_id"], "status": "public",
                      "phone_masked": mask_phone(lead.get("phone", ""))})
    return {"items": items}


# ---------------------------------------------------------------- esign
@router.post("/esign/callback")
def esign_callback(request: Request, body: dict = Body(default={})):
    secret = esign_secret()
    payload = body.get("payload") or {}
    if not verify_signature(secret, payload, body.get("signature", "")):
        raise HTTPException(status_code=401, detail={"code": "ESIGN_INVALID_SIGNATURE"})
    db = _db(request)
    contract = db["contracts"].get(payload.get("contract_id"))
    if not contract:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
    contract["status"] = "signed"
    contract["signed_at"] = payload.get("signed_at")
    contract["esign_ref"] = payload.get("esign_ref")
    db["esign_events"].append({"payload": payload})
    return {"ok": True, "contract_id": contract["id"]}


# ---------------------------------------------------------------- app factory
WRITE_METHODS = ("POST", "PUT", "PATCH")


def create_app():
    app = FastAPI(title="S3-SALES-056 招商模块", version="1.0.0")
    app.state.db = new_db()

    @app.middleware("http")
    async def readonly_amount_guard(request, call_next):
        """所有 /api/sales/ 写请求统一拦截派生金额字段（含电子签回调）。"""
        if request.method in WRITE_METHODS and request.url.path.startswith("/api/sales/"):
            raw = await request.body()
            if raw:
                try:
                    payload = json.loads(raw)
                except ValueError:
                    payload = None
                if isinstance(payload, dict):
                    bad = [f for f in money.READONLY_AMOUNT_FIELDS if f in payload]
                    if bad:
                        return JSONResponse(status_code=422,
                                            content={"detail": {"code": "READONLY_FIELD",
                                                                "fields": bad}})
                cached = raw

                async def receive():  # 把已读的 body 还给下游
                    return {"type": "http.request", "body": cached, "more_body": False}
                request._receive = receive
        return await call_next(request)

    app.include_router(router)
    return app


app = create_app()
