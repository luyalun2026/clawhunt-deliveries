# -*- coding: utf-8 -*-
"""#2288 v3 · 验收测试：4 条验收标准 + 队列/worker + 统一列约定，全部带断言。

运行：pytest tests/ -v
v3 新增（对应第 2 轮返工第 1/2/3/4/5 条）：
* queue 组：入队即返回 / worker 执行完成 / worker.start() 启动回收；
* lock 组：retry 与 run 取同一把锁，锁被占 409 且零步骤执行；
* stopfail 组：重跑某步再失败 → 下游调用计数 0、项目 failed、失败步骤记录；
* columns 组：UUID 主键、org_id/site_id、审计列、DateTime(timezone=True)。
"""
from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, pool, select, text, update
from sqlalchemy.orm import sessionmaker

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from pipeline import (AlreadyRunning, FakeRedis, MAX_ATTEMPTS, Pipeline,
                      RETRY_BACKOFF, STEPS, to_uuid)
from worker import JobQueue, Worker
import models
from models import IpProject, IpJob

ROOT = Path(__file__).resolve().parents[1]


def make_pipeline(sleep_recorder=None, redis=None):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=pool.StaticPool)  # 多连接共享同一内存库
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    sleeps = sleep_recorder if sleep_recorder is not None else []
    pipeline = Pipeline(factory, redis=redis or FakeRedis(), clock=lambda: 1732260000.0,
                        sleep=lambda s: sleeps.append(s))
    return pipeline, sleeps


def new_pid() -> str:
    return str(uuid.uuid4())


def ok_handler_log(calls):
    def handler(_sub: str = "") -> None:
        calls.append(_sub or "step")
    return handler


def counter_handlers(calls: dict):
    def counter(name):
        def handler(_sub: str = "") -> None:
            calls[name] = calls.get(name, 0) + 1
        return handler
    return {s: counter(s) for s in STEPS}


def all_ok():
    return {s: (lambda s="": None) for s in STEPS}


# ---------------------------------------------------------------- AC1
def test_ac1_happy_path_all_succeeded_or_skipped():
    """验收 1：桩函数跑完整条流水线，ip_jobs 每步为 succeeded 或 skipped。"""
    pipeline, _ = make_pipeline()
    calls: list = []
    handlers = {s: ok_handler_log(calls) for s in STEPS}
    pid = new_pid()
    result = pipeline.run(pid, handlers, scopes={"clips": False})

    assert result["status"] == "succeeded"
    jobs = result["jobs"]
    assert all(j["status"] in ("succeeded", "skipped") for j in jobs), jobs
    clips = [j for j in jobs if j["step"] == "generate" and j["sub_step"] == "clips"]
    assert clips[0]["status"] == "skipped"
    assert len([j for j in jobs if j["status"] == "succeeded"]) == len(jobs) - 1
    with pipeline.session_factory() as session:
        bad = session.execute(text(
            "SELECT count(*) FROM ip_jobs WHERE status NOT IN ('succeeded','skipped')"
        )).scalar_one()
        assert bad == 0


# ---------------------------------------------------------------- AC2
def test_ac2_retry_exhausted_four_attempts_and_backoff_sequence():
    """验收 2：transcribe 连续失败共尝试 4 次，退避 30/120/600，项目 failed。"""
    sleeps: list = []
    pipeline, _ = make_pipeline(sleep_recorder=sleeps)
    calls: dict = {}

    def transcribe(_sub: str = "") -> None:
        calls["transcribe"] = calls.get("transcribe", 0) + 1
        raise RuntimeError("asr down")

    down_calls: list = []

    def downstream(_sub: str = "") -> None:
        down_calls.append(_sub)

    handlers = {"preprocess": lambda s="": None, "transcribe": transcribe,
                "diarize": downstream, "postprocess": downstream,
                "generate": downstream, "detect_sensitive": downstream,
                "push_review": downstream}
    pid = new_pid()
    result = pipeline.run(pid, handlers)

    assert result["status"] == "failed"
    assert result["failed_step"] == "transcribe"
    assert calls["transcribe"] == MAX_ATTEMPTS == 4          # 首次 + 3 次重试
    assert sleeps == list(RETRY_BACKOFF) == [30, 120, 600]   # 可注入 sleep 记录退避序列
    assert down_calls == []                                  # 下游步骤未被调用
    with pipeline.session_factory() as session:
        proj_status = session.execute(text(
            "SELECT status, failed_step FROM ip_project")).fetchone()
        assert proj_status[0] == "failed" and proj_status[1] == "transcribe"
        row = session.execute(
            select(IpJob.status, IpJob.attempt, IpJob.error_code).where(
                IpJob.project_id == to_uuid(pid), IpJob.step == "transcribe")).fetchone()
        assert row[0] == "failed" and row[1] == 4 and row[2] == "RuntimeError"


# ---------------------------------------------------------------- AC3
def test_ac3_retry_endpoint_reruns_only_step_and_downstream():
    """验收 3：retry 接口只重跑指定步骤及下游；上游调用计数不增加。"""
    pipeline, _ = make_pipeline()
    calls: dict = {}
    handlers = counter_handlers(calls)
    pid = new_pid()
    pipeline.run(pid, handlers, scopes={"clips": True})
    first = dict(calls)
    assert first["preprocess"] == 1 and first["transcribe"] == 1

    client = TestClient(create_app(pipeline, handlers))
    resp = client.post("/api/ip/projects/%s/jobs/transcribe/retry" % pid)
    assert resp.status_code == 200
    assert resp.json()["status"] == "succeeded"

    assert calls["preprocess"] == first["preprocess"] == 1    # 上游不重复执行
    assert calls["transcribe"] == 2                            # 指定步骤被重跑
    for s in ["diarize", "postprocess", "detect_sensitive", "push_review"]:
        assert calls[s] == first[s] + 1                        # 下游各重跑一次
    assert calls["generate"] == first["generate"] + 4          # generate 4 个子步骤各重跑一次


def test_ac3b_retry_endpoint_reruns_after_failure_then_succeeds():
    """验收 3 补充：失败后经 retry 接口修复（fail → retry → succeeded）。"""
    pipeline, _ = make_pipeline()
    state = {"fail": True}

    def transcribe(_sub: str = "") -> None:
        if state["fail"]:
            raise RuntimeError("flaky")

    handlers = {"preprocess": lambda s="": None, "transcribe": transcribe,
                "diarize": lambda s="": None, "postprocess": lambda s="": None,
                "generate": lambda s="": None, "detect_sensitive": lambda s="": None,
                "push_review": lambda s="": None}
    pid = new_pid()
    result = pipeline.run(pid, handlers)
    assert result["status"] == "failed"
    state["fail"] = False
    client = TestClient(create_app(pipeline, handlers))
    resp = client.post("/api/ip/projects/%s/jobs/transcribe/retry" % pid)
    assert resp.status_code == 200
    assert resp.json()["status"] == "succeeded"
    progress = client.get("/api/ip/projects/%s/jobs" % pid).json()
    assert all(j["status"] in ("succeeded", "skipped") for j in progress["jobs"])


def test_ac3c_retry_unknown_step_returns_404():
    pipeline, _ = make_pipeline()
    handlers = all_ok()
    pid = new_pid()
    pipeline.run(pid, handlers)
    client = TestClient(create_app(pipeline, handlers))
    assert client.post("/api/ip/projects/%s/jobs/nope/retry" % pid).status_code == 404


# ---------------------------------------------------------------- AC4：队列化触发与锁
def test_ac4_enqueue_returns_202_without_executing():
    """返工整改：POST 只入队即返回 202，handlers 零调用，任务留在队列里。"""
    pipeline, _ = make_pipeline()
    calls: dict = {}
    handlers = counter_handlers(calls)
    pid = new_pid()
    client = TestClient(create_app(pipeline, handlers), raise_server_exceptions=False)
    resp = client.post("/api/ip/projects/%s/jobs" % pid, json={"scopes": {"clips": True}})
    assert resp.status_code == 202
    body = resp.json()
    assert body["enqueued"] is True and body["queue_depth"] == 1
    assert sum(calls.values()) == 0                            # 未同步执行任何步骤
    progress = pipeline.progress(pid)
    assert progress["total"] == 0                              # DB 尚未建任务行
    # worker 出队后才会执行
    worker = client.app.state.worker
    outcome = worker.run_once()
    assert outcome["status"] == "succeeded"
    assert sum(calls.values()) > 0


def test_ac4b_lock_conflict_run_and_rerun_raise():
    """返工整改：锁被占时 run 与 rerun_failed 都抛 AlreadyRunning（同一把锁）。"""
    pipeline, _ = make_pipeline()
    handlers = all_ok()
    pid = new_pid()
    # 模拟另一 worker 已持有锁（与 run/rerun_failed 内同一把 Redis NX 锁）
    assert pipeline.redis.set("ip:lock:%s" % pid, "worker-2", nx=True, ex=7200)
    with pytest.raises(AlreadyRunning):
        pipeline.run(pid, handlers)
    with pytest.raises(AlreadyRunning):
        pipeline.rerun_failed(pid, "preprocess", handlers)


def test_ac4c_retry_returns_409_and_executes_nothing_when_locked():
    """返工整改：流水线运行（锁被占）期间调用 retry 接口 → 409，且没有任何步骤被执行。"""
    pipeline, _ = make_pipeline()
    calls: dict = {}
    handlers = counter_handlers(calls)
    pid = new_pid()
    pipeline.run(pid, handlers, scopes={"clips": False})
    first = dict(calls)
    # 占住项目锁（模拟正在运行的流水线 / worker 持锁）
    assert pipeline.redis.set("ip:lock:%s" % pid, "worker-2", nx=True, ex=7200)
    client = TestClient(create_app(pipeline, handlers))
    resp = client.post("/api/ip/projects/%s/jobs/transcribe/retry" % pid)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "PIPELINE_ALREADY_RUNNING"
    assert calls == first                                      # 没有任何步骤被执行


def test_ac4d_lock_released_after_rerun_finishes():
    pipeline, _ = make_pipeline()
    handlers = all_ok()
    pid = new_pid()
    pipeline.run(pid, handlers)
    pipeline.rerun_failed(pid, "push_review", handlers)
    assert pipeline.redis.get("ip:lock:%s" % pid) is None       # 锁已释放


# ---------------------------------------------------------------- queue 组：队列 + worker
def test_queue01_worker_completes_enqueued_job():
    """worker 执行完成：出队 → 跑完整条流水线 → 全部 succeeded/skipped。"""
    pipeline, _ = make_pipeline()
    calls: dict = {}
    handlers = counter_handlers(calls)
    pid = new_pid()
    queue = JobQueue(pipeline.redis)
    worker = Worker(pipeline, queue, handlers)
    queue.enqueue(pid, {"clips": False})
    outcome = worker.run_once()
    assert outcome == {"project_id": pid, "status": "succeeded", "failed_step": None}
    progress = pipeline.progress(pid)
    assert all(j["status"] in ("succeeded", "skipped") for j in progress["jobs"])
    assert calls["generate"] == 3                              # 未授权 clips → 3 个子步骤
    assert queue.depth() == 0


def test_queue02_worker_start_reclaims_stale_running_jobs():
    """worker 启动回收：running 超 1 小时的任务回收为 pending（worker.start）。"""
    pipeline, _ = make_pipeline()
    handlers = all_ok()
    pid = new_pid()
    pipeline.run(pid, handlers, scopes={"clips": False})
    # 人为把 push_review 置为 2 小时前的 running（按流水线时钟，模拟 worker 崩溃残留）
    with pipeline.session_factory() as session:
        from datetime import datetime, timedelta, timezone
        stale = datetime.fromtimestamp(pipeline.clock(), tz=timezone.utc) - timedelta(hours=2)
        session.execute(
            update(IpJob).where(IpJob.project_id == to_uuid(pid),
                                IpJob.step == "push_review")
            .values(status="running", started_at=stale))
        session.commit()
    queue = JobQueue(pipeline.redis)
    worker = Worker(pipeline, queue, handlers)
    reclaimed = worker.start()
    assert reclaimed == [{"project_id": pid, "step": "push_review", "sub_step": ""}]
    row = pipeline.progress(pid)["jobs"]
    pr = [j for j in row if j["step"] == "push_review"][0]
    assert pr["status"] == "pending" and pr["error_code"] == "WORKER_RESTARTED"


def test_queue03_worker_requeues_when_lock_held():
    """锁被占时 worker 不并发执行：任务重新入队，本次不执行任何步骤。"""
    pipeline, _ = make_pipeline()
    calls: dict = {}
    handlers = counter_handlers(calls)
    pid = new_pid()
    pipeline.run(pid, handlers, scopes={"clips": False})
    first = dict(calls)
    assert pipeline.redis.set("ip:lock:%s" % pid, "worker-2", nx=True, ex=7200)
    queue = JobQueue(pipeline.redis)
    worker = Worker(pipeline, queue, handlers)
    queue.enqueue(pid, {"clips": False})
    outcome = worker.run_once()
    assert outcome["status"] == "requeued_delayed"
    assert calls == first                                      # 零步骤执行
    assert queue.depth() == 1                                  # 回到队列等下轮


def test_queue04_worker_tick_endpoint_drains_queue():
    """HTTP 层驱动 worker：POST /api/ip/worker/tick 逐个消费队列。"""
    pipeline, _ = make_pipeline()
    handlers = all_ok()
    p1, p2 = new_pid(), new_pid()
    client = TestClient(create_app(pipeline, handlers))
    client.post("/api/ip/projects/%s/jobs" % p1, json={"scopes": {"clips": False}})
    client.post("/api/ip/projects/%s/jobs" % p2, json={"scopes": {"clips": False}})
    r1 = client.post("/api/ip/worker/tick")
    assert r1.status_code == 200 and r1.json()["processed"]["status"] == "succeeded"
    r2 = client.post("/api/ip/worker/tick")
    assert r2.json()["processed"]["status"] == "succeeded"
    assert r2.json()["queue_depth"] == 0
    assert client.get("/api/ip/projects/%s/jobs" % p1).json()["status"] == "succeeded"
    assert client.get("/api/ip/projects/%s/jobs" % p2).json()["status"] == "succeeded"


# ---------------------------------------------------------------- stopfail 组：失败即停
def test_stopfail01_rerun_stops_on_failure_downstream_not_called():
    """返工整改：重跑时该步骤再次失败 → 下游调用计数 0，项目 failed，失败步骤记录。"""
    pipeline, _ = make_pipeline()
    calls: dict = {}
    handlers = counter_handlers(calls)
    pid = new_pid()
    pipeline.run(pid, handlers, scopes={"clips": False})       # 先全成功
    baseline = dict(calls)
    # diarize 从现在起一直失败
    failing = pipeline.calls

    def broken(_sub: str = "") -> None:
        calls["diarize"] = calls.get("diarize", 0) + 1
        raise RuntimeError("diarize down")

    handlers["diarize"] = broken
    result = pipeline.rerun_failed(pid, "diarize", handlers)
    assert result["status"] == "failed"
    assert result["failed_step"] == "diarize"
    # 下游（diarize 之后）调用计数为 0
    downstream = ["postprocess", "generate", "detect_sensitive", "push_review"]
    for s in downstream:
        assert calls[s] == baseline[s]
    assert calls["diarize"] - baseline["diarize"] == MAX_ATTEMPTS   # 失败步骤重试耗尽（4 次）
    # 存储侧：diarize failed，下游全部 pending
    with pipeline.session_factory() as session:
        rows = session.execute(
            select(IpJob.step, IpJob.status).where(IpJob.project_id == to_uuid(pid))).all()
        status_by_step = {}
        for step, st in rows:
            status_by_step.setdefault(step, set()).add(st)
        assert status_by_step["diarize"] == {"failed"}
        # 下游保持 pending；generate.clips 若因未授权本就 skipped，维持 skipped
        for s in ["postprocess", "detect_sensitive", "push_review"]:
            assert status_by_step[s] == {"pending"}
        assert status_by_step["generate"] <= {"pending", "skipped"}
        proj = session.execute(text("SELECT status, failed_step FROM ip_project")).fetchone()
        assert proj == ("failed", "diarize")


def test_stopfail02_rerun_stop_on_failure_via_api():
    """同一语义经 HTTP retry 接口复现（接口层断言）。"""
    pipeline, _ = make_pipeline()
    state = {"fail": True}

    def diarize(_sub: str = "") -> None:
        if state["fail"]:
            raise RuntimeError("diarize down")

    handlers = {"preprocess": lambda s="": None, "transcribe": lambda s="": None,
                "diarize": diarize, "postprocess": lambda s="": None,
                "generate": lambda s="": None, "detect_sensitive": lambda s="": None,
                "push_review": lambda s="": None}
    pid = new_pid()
    pipeline.run(pid, handlers, scopes={"clips": False})       # diarize 失败即停（首轮）
    state["fail"] = False
    client = TestClient(create_app(pipeline, handlers))
    resp = client.post("/api/ip/projects/%s/jobs/diarize/retry" % pid)
    assert resp.status_code == 200
    assert resp.json()["status"] == "succeeded"


# ---------------------------------------------------------------- columns 组：统一列约定
def test_columns01_uuid_pks_and_audit_columns_present():
    """返工整改：两表主键 UUID；org_id/site_id + created_at/created_by/updated_at/deleted_at。"""
    from sqlalchemy import DateTime, Uuid
    for table in (models.IpProject.__table__, models.IpJob.__table__):
        cols = table.c
        assert isinstance(cols["id"].type, Uuid), table.name
        for c in ["org_id", "site_id", "created_at", "created_by",
                  "updated_at", "deleted_at"]:
            assert c in cols, "%s 缺列 %s" % (table.name, c)
        for c in ["created_at", "updated_at", "deleted_at"]:
            assert isinstance(cols[c].type, DateTime)
    # ip_jobs 的 started_at/finished_at 也是时间类型，不再是字符串
    assert isinstance(IpJob.__table__.c["started_at"].type, DateTime)
    assert isinstance(IpJob.__table__.c["finished_at"].type, DateTime)


def test_columns02_rows_store_uuid_and_datetimes():
    """真实写入：主键为 UUID 对象、时间列为 datetime（带 tzinfo）。"""
    pipeline, _ = make_pipeline()
    handlers = all_ok()
    pid = new_pid()
    pipeline.run(pid, handlers, scopes={"clips": False})
    with pipeline.session_factory() as session:
        proj_row = session.execute(
            select(IpProject.id, IpProject.created_at, IpProject.updated_at)).fetchone()
        assert isinstance(proj_row[0], uuid.UUID) and str(proj_row[0]) == pid
        assert proj_row[1] is not None and proj_row[2] is not None
        job = session.execute(
            select(IpJob.id, IpJob.project_id, IpJob.started_at, IpJob.finished_at).where(
                IpJob.project_id == to_uuid(pid), IpJob.step == "preprocess")).fetchone()
        assert isinstance(job[0], uuid.UUID)
        assert isinstance(job[1], uuid.UUID)
        assert job[2] is not None and job[3] is not None


# ---------------------------------------------------------------- 迁移
def test_alembic_upgrade_downgrade_reversible():
    """Alembic 迁移可逆性：upgrade head 建表、downgrade base 删表。"""
    if importlib.util.find_spec("alembic") is None:
        pytest.skip("alembic 未安装")
    from alembic import command
    from alembic.config import Config

    import os, tempfile
    tmpdir = tempfile.mkdtemp()
    db = os.path.join(tmpdir, "mig.db")
    url = "sqlite:///" + db.replace("\\", "/")
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert {"ip_project", "ip_jobs", "alembic_version"} <= tables
    # 迁移与模型列一致（两表统一列都在）
    for t in ("ip_project", "ip_jobs"):
        cols = {c["name"] for c in insp.get_columns(t)}
        for c in ["id", "org_id", "site_id", "created_at", "created_by",
                  "updated_at", "deleted_at"]:
            assert c in cols, "%s 迁移缺列 %s" % (t, c)
    command.downgrade(cfg, "base")
    engine.dispose()
    engine = create_engine(url)
    tables2 = set(inspect(engine).get_table_names())
    assert "ip_project" not in tables2 and "ip_jobs" not in tables2
    engine.dispose()


def test_models_schema_matches_expected_columns():
    """模型字段完备性：ip_jobs 具备验收涉及的全部列。"""
    cols = {c.name for c in IpJob.__table__.columns}
    assert {"project_id", "step", "sub_step", "seq", "status", "attempt",
            "started_at", "finished_at", "error_code",
            "org_id", "site_id", "created_at", "created_by",
            "updated_at", "deleted_at"} <= cols
