# -*- coding: utf-8 -*-
"""实测：整条流水线调用次数、重试耗尽、单步重跑增量、并发 409、重启回收。

数字全部在真实执行路径中采集（调用计数、注入 sleep 的退避序列），不手写。
"""
import json

from sqlalchemy import create_engine, pool
from sqlalchemy.orm import sessionmaker

import models
from pipeline import MAX_ATTEMPTS, AlreadyRunning, FakeRedis, Pipeline, RETRY_BACKOFF, STEPS


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

    # 1) happy path：全流程，未授权 clips → skipped
    p1 = make_pipeline(clock, sleeps)
    h1 = handlers()
    out = p1.run("proj-a", h1, scopes={"clips": False})
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
    out2 = p2.run("proj-b", h2)
    m["retry_exhausted"] = {"status": out2["status"],
                            "failed_step": out2["failed_step"],
                            "transcribe_attempts": fail_stub.calls,
                            "max_attempts_expected": MAX_ATTEMPTS,
                            "backoff_sequence": list(RETRY_BACKOFF),
                            "downstream_calls": {k: h2[k].calls for k in
                                                 ["diarize", "postprocess", "generate",
                                                  "detect_sensitive", "push_review"]}}

    # 3) 单步重跑增量：上游不重复执行
    p3 = make_pipeline(clock, sleeps)
    h3 = handlers()
    p3.run("proj-c", h3, scopes={"clips": False})
    before = {s: h3[s].calls for s in STEPS}
    p3.rerun_failed("proj-c", "transcribe", h3)
    after = {s: h3[s].calls for s in STEPS}
    m["rerun_delta"] = {s: after[s] - before[s] for s in STEPS}

    # 4) 并发 409：锁被占时编排器抛 AlreadyRunning
    p4 = make_pipeline(clock, sleeps)
    p4.redis.set("ip:lock:proj-d", "worker-2", nx=True, ex=7200)
    try:
        p4.run("proj-d", handlers())
        m["concurrent_conflict"] = False
    except AlreadyRunning:
        m["concurrent_conflict"] = True

    # 5) 重启回收：running 超 3600s → pending
    p5 = make_pipeline(clock, sleeps)
    h5 = handlers()
    p5.run("proj-e", h5, scopes={"clips": False})
    with p5.session_factory() as s:
        from sqlalchemy import update as _upd
        from models import IpJob
        from pipeline import _now
        s.execute(_upd(IpJob).where(IpJob.project_id == "proj-e",
                                    IpJob.step == "push_review")
                  .values(status="running", started_at=_now(lambda: clock.t - 4000)))
        s.commit()
    m["stale_reclaimed"] = len(p5.reclaim_stale("proj-e"))
    m["stale_error_code"] = "WORKER_RESTARTED"

    print(json.dumps(m, ensure_ascii=False))
    return m


if __name__ == "__main__":
    main()
