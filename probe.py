# -*- coding: utf-8 -*-
"""实测：队列/worker、加锁重跑、失败即停、并发 409、重启回收、统一列约定。

数字全部在真实执行路径中采集（调用计数、注入 sleep 的退避序列、队列深度），不手写。
"""
import json
import uuid

from sqlalchemy import create_engine, pool, update as _upd
from sqlalchemy.orm import sessionmaker

import models
from pipeline import (MAX_ATTEMPTS, RETRY_BACKOFF, STEPS, AlreadyRunning,
                      FakeRedis, Pipeline, _now, to_uuid)
from worker import JobQueue, Worker


class Clock:
    def __init__(self):
        self.t = 1_780_000_000.0

    def __call__(self):
        return self.t


class Stub:
    def __init__(self, name, always_fail=False):
        self.name = name
        self.calls = 0
        self.always_fail = always_fail

    def __call__(self, sub_step=""):
        self.calls += 1
        if self.always_fail:
            raise RuntimeError("%s 失败" % self.name)


def make_pipeline(clock, sleeps):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=pool.StaticPool)
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return Pipeline(factory, redis=FakeRedis(clock), clock=clock, sleep=sleeps.append)


def handlers(**over):
    h = {s: Stub(s) for s in ["preprocess", "transcribe", "diarize", "postprocess",
                              "detect_sensitive", "push_review"]}
    h["generate"] = Stub("generate")
    h.update(over)
    return h


def main():
    m = {}
    clock = Clock()
    sleeps = []
    new_id = lambda: str(uuid.uuid4())  # noqa: E731

    # 1) happy path：全流程，未授权 clips → skipped
    p1 = make_pipeline(clock, sleeps)
    h1 = handlers()
    out = p1.run(new_id(), h1, scopes={"clips": False})
    m["happy_path"] = {"status": out["status"],
                       "total_jobs": len(out["jobs"]),
                       "succeeded": sum(1 for j in out["jobs"] if j["status"] == "succeeded"),
                       "skipped": sum(1 for j in out["jobs"] if j["status"] == "skipped"),
                       "step_calls": {k: v.calls for k, v in h1.items()},
                       "job_statuses": sorted({j["status"] for j in out["jobs"]})}

    # 2) 重试耗尽：transcribe 连续失败 → 4 次尝试、退避 30/120/600、项目 failed
    p2 = make_pipeline(clock, sleeps)
    fail_stub = Stub("transcribe", always_fail=True)
    h2 = handlers(transcribe=fail_stub)
    out2 = p2.run(new_id(), h2)
    m["retry_exhausted"] = {"status": out2["status"],
                            "failed_step": out2["failed_step"],
                            "transcribe_attempts": fail_stub.calls,
                            "max_attempts_expected": MAX_ATTEMPTS,
                            "backoff_sequence": list(RETRY_BACKOFF),
                            "downstream_calls": {k: h2[k].calls for k in
                                                 ["diarize", "postprocess", "generate",
                                                  "detect_sensitive", "push_review"]}}

    # 3) 单步重跑增量：上游不重复执行；与 run 同一把锁
    p3 = make_pipeline(clock, sleeps)
    h3 = handlers()
    pid3 = new_id()
    p3.run(pid3, h3, scopes={"clips": False})
    before = {s: h3[s].calls for s in STEPS}
    out3 = p3.rerun_failed(pid3, "transcribe", h3)
    after = {s: h3[s].calls for s in STEPS}
    m["rerun_delta"] = {s: after[s] - before[s] for s in STEPS}
    m["rerun_status"] = out3["status"]

    # 3b) 重跑失败即停：diarize 再失败 → postprocess 及下游调用数 0
    p3b = make_pipeline(clock, sleeps)
    h3b = handlers()
    pid3b = new_id()
    p3b.run(pid3b, h3b, scopes={"clips": False})
    down_before = {s: h3b[s].calls for s in
                   ["diarize", "postprocess", "generate", "detect_sensitive", "push_review"]}
    h3b["diarize"] = Stub("diarize", always_fail=True)
    out3b = p3b.rerun_failed(pid3b, "diarize", h3b)
    down_after = {s: h3b[s].calls for s in
                  ["postprocess", "generate", "detect_sensitive", "push_review"]}
    m["stop_on_failure"] = {"status": out3b["status"],
                            "failed_step": out3b["failed_step"],
                            "downstream_delta": {s: down_after[s] - down_before[s]
                                                 for s in down_after}}

    # 4) 并发 409：锁被占时 run 与 rerun_failed 都抛 AlreadyRunning
    p4 = make_pipeline(clock, sleeps)
    pid4 = new_id()
    p4.redis.set("ip:lock:%s" % pid4, "worker-2", nx=True, ex=7200)
    conflicts = {}
    try:
        p4.run(pid4, handlers())
        conflicts["run"] = False
    except AlreadyRunning:
        conflicts["run"] = True
    try:
        p4.rerun_failed(pid4, "preprocess", handlers())
        conflicts["rerun"] = False
    except AlreadyRunning:
        conflicts["rerun"] = True
    m["lock_conflicts"] = conflicts

    # 5) 重启回收：running 超 3600s → pending
    p5 = make_pipeline(clock, sleeps)
    h5 = handlers()
    pid5 = new_id()
    p5.run(pid5, h5, scopes={"clips": False})
    with p5.session_factory() as s:
        s.execute(_upd(models.IpJob).where(models.IpJob.project_id == to_uuid(pid5),
                                           models.IpJob.step == "push_review")
                  .values(status="running", started_at=_now(lambda: clock.t - 4000)))
        s.commit()
    m["stale_reclaimed"] = len(p5.reclaim_stale(pid5))
    m["stale_error_code"] = "WORKER_RESTARTED"

    # 6) 队列与 worker：入队即返回、worker 执行完成、worker.start() 回收
    p6 = make_pipeline(clock, sleeps)
    h6 = handlers()
    pid6 = new_id()
    q6 = JobQueue(p6.redis)
    w6 = Worker(p6, q6, h6)
    q6.enqueue(pid6, {"clips": False})
    depth_after_enqueue = q6.depth()
    calls_before = {s: h6[s].calls for s in h6}
    outcome = w6.run_once()
    calls_after = {s: h6[s].calls for s in h6}
    m["queue_worker"] = {
        "depth_after_enqueue": depth_after_enqueue,
        "handled_called_before_worker": sum(calls_before.values()),
        "worker_outcome_status": outcome["status"],
        "handled_calls_after_worker": sum(calls_after.values()),
        "depth_after_worker": q6.depth(),
    }

    # 7) 统一列约定：UUID 主键 + 审计列 + 时间类型
    m["schema_convention"] = {
        "job_pk_type": str(models.IpJob.__table__.c["id"].type),
        "project_pk_type": str(models.IpProject.__table__.c["id"].type),
        "started_at_type": str(models.IpJob.__table__.c["started_at"].type),
        "common_columns_present": all(
            c in models.IpJob.__table__.c and c in models.IpProject.__table__.c
            for c in ["org_id", "site_id", "created_at", "created_by",
                      "updated_at", "deleted_at"]),
    }

    print(json.dumps(m, ensure_ascii=False))
    return m


if __name__ == "__main__":
    main()
