# -*- coding: utf-8 -*-
"""FastAPI 接口：GET /api/sop/templates/{id}/export 与 POST /api/sop/templates/import。"""
from __future__ import annotations
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import sop_core

app = FastAPI(title="SOP Template API", version="1.0")

STORE: dict = {}
CATALOGS = sop_core.load_catalogs()


class ImportPayload(BaseModel):
    payload: dict


@app.post("/api/sop/templates/import")
def import_template(body: ImportPayload):
    result = sop_core.import_template(body.payload, CATALOGS, STORE)
    return result


@app.get("/api/sop/templates/{tid}/export")
def export_template(tid: str):
    doc = sop_core.export_template(tid, STORE)
    if doc is None:
        raise HTTPException(status_code=404, detail="template not found")
    return doc
