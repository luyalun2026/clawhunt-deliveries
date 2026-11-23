# -*- coding: utf-8 -*-
"""#2288 v3 · FastAPI 接口层（队列化触发 + 加锁重跑 + 只写已实现行为）。

v3 整改（对应第 2 轮返工第 1/2/5 条）：
* POST /api/ip/projects/{id}/jobs  → **只入队即返回 202**（进程内 Redis 替身队列），
  由 worker 取出执行（见 worker.py）；不再在请求内同步跑完整条流水线；
* POST /api/ip/projects/{id}/jobs/{step}/retry → rerun_failed 取与 run() 相同的
  `ip:lock:<project_id>` 锁，锁被占返回 409 PIPELINE_ALREADY_RUNNING（有测试）；
* POST /api/ip/worker/tick         → 驱动 worker 出队执行一个任务（运维/测试入口）；
* GET  /api/ip/projects/{id}/jobs  → ip_jobs 逐步状态。

接口说明只写已实现且有测试覆盖的行为（返工意见 #5）。
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Callable, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from pipeline import AlreadyRunning, Pipeline
from worker import JobQueue, Worker

Handlers = Dict[str, Callable[[str], None]]


class TriggerIn(BaseModel):
    scopes: Dict[str, bool] = Field(default_factory=lambda: {"clips": True})


def create_app(pipeline: Pipeline, handlers: Optional[Handlers] = None,
               run_worker_on_start: bool = True) -> FastAPI:
    state_handlers: Handlers = handlers if handlers is not None else _default_handlers()
    queue = JobQueue(pipeline.redis)
    worker = Worker(pipeline, queue, state_handlers)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # worker 启动流程：回收 running 超 1 小时的任务为 pending
        if run_worker_on_start:
            worker.start()
        yield

    app = FastAPI(title="IP pipeline #2288 v3", lifespan=lifespan)
    app.state.pipeline = pipeline
    app.state.handlers = state_handlers
    app.state.queue = queue
    app.state.worker = worker

    def _pid(project_id: str) -> uuid.UUID:
        try:
            return uuid.UUID(project_id)
        except ValueError:
            raise HTTPException(status_code=422,
                                detail={"code": "INVALID_PROJECT_ID", "project_id": project_id})

    @app.post("/api/ip/projects/{project_id}/jobs", status_code=202)
    def trigger(project_id: str, body: Optional[TriggerIn] = None) -> dict:
        """只入队即返回（202）；执行由 worker 完成。"""
        pid = _pid(project_id)
        scopes = body.scopes if body is not None else {"clips": True}
        depth = queue.enqueue(str(pid), scopes)
        return {"enqueued": True, "project_id": str(pid), "queue_depth": depth}

    @app.post("/api/ip/projects/{project_id}/jobs/{step}/retry")
    def retry(project_id: str, step: str) -> dict:
        pid = _pid(project_id)
        if step not in state_handlers:
            raise HTTPException(status_code=404,
                                detail={"code": "UNKNOWN_STEP", "step": step})
        try:
            return pipeline.rerun_failed(pid, step, state_handlers)
        except AlreadyRunning:
            raise HTTPException(status_code=409,
                                detail={"code": "PIPELINE_ALREADY_RUNNING"})
        except KeyError:
            raise HTTPException(status_code=404,
                                detail={"code": "UNKNOWN_STEP", "step": step})

    @app.post("/api/ip/worker/tick")
    def worker_tick() -> dict:
        """驱动 worker 出队执行一个任务（生产由常驻 worker 进程调用）。"""
        result = worker.run_once()
        return {"processed": result, "queue_depth": queue.depth()}

    @app.get("/api/ip/worker/queue")
    def worker_queue() -> dict:
        return {"queue_depth": queue.depth()}

    @app.get("/api/ip/projects/{project_id}/jobs")
    def jobs(project_id: str) -> dict:
        return pipeline.progress(_pid(project_id))

    return app


def _default_handlers() -> Handlers:
    """演示桩：全部成功；生产环境在 create_app 传入真实 handler 覆盖。"""
    def ok(_sub: str = "") -> None:
        return None
    return {s: ok for s in ["preprocess", "transcribe", "diarize", "postprocess",
                            "generate", "detect_sensitive", "push_review"]}
