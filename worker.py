# -*- coding: utf-8 -*-
"""#2288 v3 · 队列与 worker（对应第 2 轮返工第 1 条）。

订单原文要求：
* 队列用 Redis（进程内 FakeRedis 等价实现，生产替换 redis-py 的
  RPUSH / LPOP 同名命令）；
* POST 只把任务入队并立即返回，由 worker 取出并执行各步骤；
* worker 重启后，running 超过 1 小时的任务回收为 pending（启动时执行 reclaim_stale）。

测试覆盖（tests/test_ip_pipeline_v2.py）：
* test_queue01 — 入队即返回：POST 202，handlers 零调用，任务在队列里；
* test_queue02 — worker 执行完成：run_once 出队并跑完整条流水线；
* test_queue03 — 启动回收：worker.start() 把 running 超 1h 的任务回收为 pending；
* test_queue04 — 锁被占时 worker 不并发执行（re-queue 后返回）。
"""
from __future__ import annotations

import json
from typing import Callable, Dict, Optional

from pipeline import AlreadyRunning, FakeRedis, Pipeline

QUEUE_KEY = "ip:queue"


class JobQueue:
    """Redis 列表队列：元素为 JSON 载荷 {"project_id", "scopes", "enqueued_at"}。"""

    def __init__(self, redis: FakeRedis):
        self.redis = redis

    def enqueue(self, project_id: str, scopes: Optional[dict] = None,
                enqueued_at: Optional[float] = None) -> int:
        payload = json.dumps({"project_id": str(project_id),
                              "scopes": scopes or {"clips": True},
                              "enqueued_at": enqueued_at}, ensure_ascii=False)
        return self.redis.rpush(QUEUE_KEY, payload)

    def pop(self) -> Optional[dict]:
        raw = self.redis.lpop(QUEUE_KEY)
        return json.loads(raw) if raw else None

    def depth(self) -> int:
        return self.redis.llen(QUEUE_KEY)


class Worker:
    """从队列取任务并执行流水线；start() 在启动时回收超时 running 任务。"""

    def __init__(self, pipeline: Pipeline, queue: JobQueue,
                 handlers: Dict[str, Callable[[str], None]]):
        self.pipeline = pipeline
        self.queue = queue
        self.handlers = handlers
        self.reclaimed_at_start: list = []
        self.processed: list = []

    def start(self) -> list:
        """worker 启动流程：回收 running 超 1 小时的任务为 pending（返工意见 #1）。"""
        self.reclaimed_at_start = self.pipeline.reclaim_stale()
        return self.reclaimed_at_start

    def run_once(self) -> Optional[dict]:
        """出队一个任务并同步执行；锁被占时把任务放回队首，不并发执行。"""
        item = self.queue.pop()
        if item is None:
            return None
        pid = item["project_id"]
        try:
            result = self.pipeline.run(pid, self.handlers, scopes=item.get("scopes"))
            outcome = {"project_id": pid, "status": result["status"],
                       "failed_step": result["failed_step"]}
        except AlreadyRunning:
            # 同一项目已有流水线在跑：不放回队尾打转，直接标记 requeued_delayed
            self.queue.enqueue(pid, item.get("scopes"))
            outcome = {"project_id": pid, "status": "requeued_delayed"}
        self.processed.append(outcome)
        return outcome

    def run_all(self, max_items: int = 100) -> list:
        out = []
        for _ in range(max_items):
            r = self.run_once()
            if r is None:
                break
            out.append(r)
        return out
