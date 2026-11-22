# -*- coding: utf-8 -*-
"""身份与签名：X-Actor-Id 头是 S2-IAM 的接口桩；密钥只从环境变量读取。"""
import hashlib
import hmac
import json
import os

from fastapi import Header, HTTPException, Request

IAM_STUB_NOTE = "S2-IAM 对接点：此处校验网关下发的 JWT，取出 user_id/org_id/role/site_id"


def esign_secret():
    """密钥只从环境变量读取；缺失即拒绝服务，绝不回落到字面量。"""
    secret = os.environ.get("ESIGN_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail={"code": "ESIGN_SECRET_MISSING"})
    return secret


def sign_payload(secret, payload):
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()


def verify_signature(secret, payload, signature):
    if not isinstance(signature, str):
        return False
    return hmac.compare_digest(sign_payload(secret, payload), signature.lower())


def current_actor(request: Request, x_actor_id: str = Header(default="", alias="X-Actor-Id")):
    db = request.app.state.db
    actor = db["users"].get(x_actor_id)
    if not actor:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED"})
    return actor
