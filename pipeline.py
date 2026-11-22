# -*- coding: utf-8 -*-
"""#2288 v2 · IP 处理流水线状态机与失败重试编排（SQLAlchemy 2 会话版）。

与 v1 的差异（按返工意见整改）：
* 存储层统一走 SQLAlchemy 2 ORM 模型（models.py），建表由 Alembic 迁移负责（migrations/）。
* Redis 锁保持进程内等价实现（FakeRedis），生产替换点：redis-py 的
  `SET ip:lock:<project_id> <owner> NX EX 7200` / `DEL`，接口语义完全一致。
* HTTP 接口层见 app.py（POST retry / GET jobs），本模块只保留编排核心。
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from models import IpJob, IpProject

STEPS = ["preprocess", "transcribe", "diarize", "postprocess", "generate",
         "detect_sensitive", "push_review"]
GENERATE_SUBSTEPS = ["chapters", "intro", "quotes", "clips"]
RETRY_BACKOFF = (30, 120, 600)          # 秒
MAX_ATTEMPTS = 1 + len(RETRY_BACKOFF)   # 首次 + 3 次重试 = 4
LOCK_TTL = 7200
STALE_SECONDS = 3600


class AlreadyRunning(Exception):
    """同一项目已有流水线在跑 → 接口层映射为 409 PIPELINE_ALREADY_RUNNING。"""


class FakeRedis:
    """带 NX / EX 语义的进程内替身；生产替换为 redis-py 同名调用（见 README）。"""

    def __init__(self, clock: Callable[[], float] = time.time):
        self.data: Dict[str, tuple] = {}
        self.clock = clock

    def set(self, key: str, value: str, nx: bool = False, ex: Optional[int] = None) -> bool:
        if nx and key in self.data and self.data[key][1] > self.clock():
            return False
        self.data[key] = (value, self.clock() + (ex or 0))
        return True

    def get(self, key: str) -> Optional[str]:
        item = self.data.get(key)
        if not item:
            return None
        if item[1] and item[1] <= self.clock():
            self.data.pop(key, None)
            return None
        return item[0]

    def delete(self, key: str) -> None:
        self.data.pop(key, None)


def _now(clock: Callable[[], float]) -> str:
    return datetime.fromtimestamp(clock()).isoformat(timespec="seconds")


class Pipeline:
    def __init__(self, session_factory: sessionmaker,
                 redis: Optional[FakeRedis] = None,
                 clock: Callable[[], float] = time.time,
                 sleep: Callable[[float], None] = time.sleep,
                 lock_owner: str = "worker-1"):
        self.session_factory = session_factory
        self.redis = redis or FakeRedis(clock)
        self.clock = clock
        self.sleep = sleep
        self.lock_owner = lock_owner
        self.calls: Dict[str, int] = {}

    # ---------------- 基础设施 ----------------
    def _ensure_project(self, session: Session, project_id: str) -> None:
        if session.get(IpProject, project_id) is None:
            session.add(IpProject(id=project_id))

    def _set_status(self, session: Session, project_id: str, step: str, sub_step: str,
                    status: str, attempt: Optional[int] = None,
                    error_code: Optional[str] = None) -> None:
        values: Dict[str, object] = {"status": status, "error_code": error_code}
        if attempt is not None:
            values["attempt"] = attempt
        if status == "running":
            values["started_at"] = _now(self.clock)
        if status in ("succeeded", "failed", "skipped"):
            values["finished_at"] = _now(self.clock)
        session.execute(update(IpJob)
                        .where(IpJob.project_id == project_id, IpJob.step == step,
                               IpJob.sub_step == sub_step)
                        .values(**values))

    def _init_rows(self, session: Session, project_id: str,
                   scopes: Dict[str, bool]) -> None:
        self._ensure_project(session, project_id)
        existing = {(r[0], r[1]) for r in session.execute(
            select(IpJob.step, IpJob.sub_step).where(IpJob.project_id == project_id)).all()}
        for seq, step in enumerate(STEPS, start=1):
            subs = GENERATE_SUBSTEPS if step == "generate" else [""]
            base = seq * 10
            for i, sub in enumerate(subs):
                if (step, sub) in existing:
                    continue
                session.add(IpJob(project_id=project_id, step=step, sub_step=sub,
                                  seq=base + i, status="pending"))
        if not scopes.get("clips", True):
            session.execute(update(IpJob)
                            .where(IpJob.project_id == project_id,
                                   IpJob.step == "generate", IpJob.sub_step == "clips")
                            .values(status="skipped", finished_at=_now(self.clock)))

    def _step_status(self, session: Session, project_id: str, step: str) -> List[str]:
        rows = session.execute(select(IpJob.status).where(
            IpJob.project_id == project_id, IpJob.step == step).order_by(IpJob.sub_step)).all()
        return [r[0] for r in rows]

    def _upstream_done(self, session: Session, project_id: str, seq: int) -> bool:
        rows = session.execute(
            select(IpJob.step, IpJob.seq).where(IpJob.project_id == project_id,
                                                IpJob.seq < seq).distinct()).all()
        for step, _seq in rows:
            if any(s not in ("succeeded", "skipped")
                   for s in self._step_status(session, project_id, step)):
                return False
        return True

    def _call(self, step: str, fn: Callable[[], object]) -> None:
        self.calls[step] = self.calls.get(step, 0) + 1
        fn()

    def _run_step(self, session: Session, project_id: str, step: str,
                  handler: Callable[[str], None], sub_step: str = "") -> bool:
        """执行单步（含重试）。返回是否最终成功。"""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._set_status(session, project_id, step, sub_step, "running", attempt=attempt)
            try:
                key = step if not sub_step else "%s.%s" % (step, sub_step)
                self._call(key, lambda: handler(sub_step))
                self._set_status(session, project_id, step, sub_step, "succeeded", attempt=attempt)
                return True
            except Exception as exc:  # noqa: BLE001 - 桩抛任何异常都按失败处理
                code = getattr(exc, "code", None) or type(exc).__name__
                if attempt < MAX_ATTEMPTS:
                    self.sleep(RETRY_BACKOFF[attempt - 1])
                    continue
                self._set_status(session, project_id, step, sub_step, "failed",
                                 attempt=attempt, error_code=str(code))
                return False
        return False

    # ---------------- 主流程 ----------------
    def run(self, project_id: str, handlers: Dict[str, Callable[[str], None]],
            scopes: Optional[Dict[str, bool]] = None) -> Dict:
        scopes = scopes or {"clips": True}
        lock_key = "ip:lock:%s" % project_id
        if not self.redis.set(lock_key, self.lock_owner, nx=True, ex=LOCK_TTL):
            raise AlreadyRunning(project_id)
        try:
            with self.session_factory() as session:
                self._init_rows(session, project_id, scopes)
                session.execute(update(IpProject).where(IpProject.id == project_id)
                                .values(status="running", failed_step=None))
                session.commit()
                failed_step = None

                for seq, step in enumerate(STEPS, start=1):
                    if not self._upstream_done(session, project_id, seq * 10):
                        break
                    if step == "generate":
                        ok = True
                        for sub in GENERATE_SUBSTEPS:
                            cur = session.execute(select(IpJob.status).where(
                                IpJob.project_id == project_id, IpJob.step == "generate",
                                IpJob.sub_step == sub)).scalar_one()
                            if cur in ("succeeded", "skipped"):
                                continue
                            if not self._run_step(session, project_id, step,
                                                  handlers["generate"], sub):
                                ok = False
                        if not ok:
                            failed_step = "generate"
                            break
                    else:
                        if not self._run_step(session, project_id, step, handlers[step]):
                            failed_step = step
                            break

                status = "failed" if failed_step else "succeeded"
                session.execute(update(IpProject).where(IpProject.id == project_id)
                                .values(status=status, failed_step=failed_step))
                session.commit()
                return {"project_id": project_id, "status": status,
                        "failed_step": failed_step, "jobs": self.progress(project_id)["jobs"]}
        finally:
            self.redis.delete(lock_key)

    # ---------------- 重跑 ----------------
    def reset_from(self, project_id: str, step: str) -> Dict:
        """把指定步骤及其下游置回 pending；上游保持 succeeded，不重复执行。"""
        if step not in STEPS:
            raise KeyError("未知步骤: %s" % step)
        downstream = [step] + STEPS[STEPS.index(step) + 1:]
        with self.session_factory() as session:
            for s in downstream:
                if s == "generate":
                    # clips 若因授权本就 skip，保持 skip
                    session.execute(update(IpJob)
                                    .where(IpJob.project_id == project_id,
                                           IpJob.step == "generate", IpJob.status != "skipped")
                                    .values(status="pending", attempt=0, error_code=None,
                                            started_at=None, finished_at=None))
                else:
                    session.execute(update(IpJob)
                                    .where(IpJob.project_id == project_id, IpJob.step == s)
                                    .values(status="pending", attempt=0, error_code=None,
                                            started_at=None, finished_at=None))
            session.execute(update(IpProject).where(IpProject.id == project_id)
                            .values(status="running", failed_step=None))
            session.commit()
        return {"project_id": project_id, "requeued": downstream}

    def rerun_failed(self, project_id: str, step: str,
                     handlers: Dict[str, Callable[[str], None]]) -> Dict:
        self.reset_from(project_id, step)
        plan_downstream = [step] + STEPS[STEPS.index(step) + 1:]
        with self.session_factory() as session:
            for s in plan_downstream:
                if s == "generate":
                    for sub in GENERATE_SUBSTEPS:
                        cur = session.execute(select(IpJob.status).where(
                            IpJob.project_id == project_id, IpJob.step == "generate",
                            IpJob.sub_step == sub)).scalar_one()
                        if cur in ("succeeded", "skipped"):
                            continue
                        self._run_step(session, project_id, "generate", handlers["generate"], sub)
                else:
                    self._run_step(session, project_id, s, handlers[s])
            failed = [r[0] for r in session.execute(
                select(IpJob.step).where(IpJob.project_id == project_id,
                                         IpJob.status == "failed").distinct()).all()]
            status = "failed" if failed else "succeeded"
            session.execute(update(IpProject).where(IpProject.id == project_id)
                            .values(status=status, failed_step=failed[0] if failed else None))
            session.commit()
        return {"project_id": project_id, "status": status,
                "failed_step": failed[0] if failed else None}

    # ---------------- 恢复与进度 ----------------
    def reclaim_stale(self, project_id: Optional[str] = None) -> List[Dict]:
        limit = datetime.fromtimestamp(self.clock()) - timedelta(seconds=STALE_SECONDS)
        out = []
        with self.session_factory() as session:
            rows = session.execute(select(IpJob).where(IpJob.status == "running")).scalars().all()
            for r in rows:
                if project_id and r.project_id != project_id:
                    continue
                started = datetime.fromisoformat(r.started_at) if r.started_at else None
                if started is None or started <= limit:
                    session.execute(update(IpJob)
                                    .where(IpJob.id == r.id)
                                    .values(status="pending", error_code="WORKER_RESTARTED"))
                    out.append({"project_id": r.project_id, "step": r.step,
                                "sub_step": r.sub_step})
            session.commit()
        return out

    def progress(self, project_id: str) -> Dict:
        with self.session_factory() as session:
            rows = session.execute(
                select(IpJob).where(IpJob.project_id == project_id)
                .order_by(IpJob.seq, IpJob.sub_step)).scalars().all()
            jobs = [{"step": r.step, "sub_step": r.sub_step, "status": r.status,
                     "attempt": r.attempt, "error_code": r.error_code} for r in rows]
            proj = session.get(IpProject, project_id)
            done = sum(1 for j in jobs if j["status"] in ("succeeded", "skipped"))
            return {"project_id": project_id, "jobs": jobs, "done": done,
                    "total": len(jobs),
                    "failed": [j["step"] for j in jobs if j["status"] == "failed"],
                    "status": proj.status if proj else "unknown"}
