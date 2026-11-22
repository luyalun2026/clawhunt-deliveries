# -*- coding: utf-8 -*-
"""#2288 v2 · FastAPI 接口层（返工意见 #2：补齐两个 HTTP 接口）。

* POST /api/ip/projects/{id}/jobs              → 触发整条流水线；锁冲突返回 409
* POST /api/ip/projects/{id}/jobs/{step}/retry → 只重跑指定步骤及下游；上游不重复执行
* GET  /api/ip/projects/{id}/jobs              → 返回 ip_jobs 逐步状态
"""
from __future__ import annotations

from typing import Callable, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from pipeline import AlreadyRunning, Pipeline

Handlers = Dict[str, Callable[[str], None]]


class TriggerIn(BaseModel):
    scopes: Dict[str, bool] = Field(default_factory=lambda: {"clips": True})


def create_app(pipeline: Pipeline, handlers: Optional[Handlers] = None) -> FastAPI:
    app = FastAPI(title="IP pipeline #2288 v2")
    state_handlers: Handlers = handlers if handlers is not None else _default_handlers()
    app.state.pipeline = pipeline
    app.state.handlers = state_handlers

    @app.post("/api/ip/projects/{project_id}/jobs", status_code=202)
    def trigger(project_id: str, body: Optional[TriggerIn] = None) -> dict:
        scopes = body.scopes if body is not None else {"clips": True}
        try:
            return pipeline.run(project_id, state_handlers, scopes=scopes)
        except AlreadyRunning:
            raise HTTPException(status_code=409,
                                detail={"code": "PIPELINE_ALREADY_RUNNING"})

    @app.post("/api/ip/projects/{project_id}/jobs/{step}/retry")
    def retry(project_id: str, step: str) -> dict:
        if step not in state_handlers:
            raise HTTPException(status_code=404,
                                detail={"code": "UNKNOWN_STEP", "step": step})
        try:
            return pipeline.rerun_failed(project_id, step, state_handlers)
        except AlreadyRunning:
            raise HTTPException(status_code=409,
                                detail={"code": "PIPELINE_ALREADY_RUNNING"})
        except KeyError:
            raise HTTPException(status_code=404,
                                detail={"code": "UNKNOWN_STEP", "step": step})

    @app.get("/api/ip/projects/{project_id}/jobs")
    def jobs(project_id: str) -> dict:
        return pipeline.progress(project_id)

    return app


def _default_handlers() -> Handlers:
    """演示桩：全部成功；生产环境在 create_app 传入真实 handler 覆盖。"""
    def ok(_sub: str = "") -> None:
        return None
    return {s: ok for s in ["preprocess", "transcribe", "diarize", "postprocess",
                            "generate", "detect_sensitive", "push_review"]}
