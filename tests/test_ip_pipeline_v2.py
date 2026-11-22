# -*- coding: utf-8 -*-
"""#2288 v2 · 验收测试：4 条验收标准全部带接口层/存储层断言。

运行：pytest tests/ -v
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, pool, text
from sqlalchemy.orm import sessionmaker

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from pipeline import AlreadyRunning, FakeRedis, MAX_ATTEMPTS, Pipeline, RETRY_BACKOFF, STEPS
import models
from models import IpJob

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


def ok_handler_log(calls):
    def handler(_sub: str = "") -> None:
        calls.append(_sub or "step")
    return handler


# ---------------------------------------------------------------- AC1
def test_ac1_happy_path_all_succeeded_or_skipped():
    """验收 1：桩函数跑完整条流水线，ip_jobs 每步为 succeeded 或 skipped。"""
    pipeline, _ = make_pipeline()
    calls: list = []
    handlers = {s: ok_handler_log(calls) for s in STEPS}
    result = pipeline.run("p1", handlers, scopes={"clips": False})

    assert result["status"] == "succeeded"
    jobs = result["jobs"]
    # generate.clips 因未授权 → skipped；其余全部 succeeded
    assert all(j["status"] in ("succeeded", "skipped") for j in jobs), jobs
    clips = [j for j in jobs if j["step"] == "generate" and j["sub_step"] == "clips"]
    assert clips[0]["status"] == "skipped"
    assert len([j for j in jobs if j["status"] == "succeeded"]) == len(jobs) - 1
    # 存储侧复核：DB 里没有任何 pending/running/failed
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
    result = pipeline.run("p2", handlers)

    assert result["status"] == "failed"
    assert result["failed_step"] == "transcribe"
    assert calls["transcribe"] == MAX_ATTEMPTS == 4          # 首次 + 3 次重试
    assert sleeps == list(RETRY_BACKOFF) == [30, 120, 600]   # 可注入 sleep 记录退避序列
    assert down_calls == []                                  # 下游步骤未被调用
    with pipeline.session_factory() as session:
        proj_status = session.execute(text(
            "SELECT status, failed_step FROM ip_project WHERE id='p2'")).fetchone()
        assert proj_status[0] == "failed" and proj_status[1] == "transcribe"
        row = session.execute(text(
            "SELECT status, attempt, error_code FROM ip_jobs "
            "WHERE project_id='p2' AND step='transcribe'")).fetchone()
        assert row[0] == "failed" and row[1] == 4 and row[2] == "RuntimeError"


# ---------------------------------------------------------------- AC3
def test_ac3_retry_endpoint_reruns_only_step_and_downstream():
    """验收 3：retry 接口只重跑指定步骤及下游；上游调用计数不增加。"""
    pipeline, _ = make_pipeline()
    calls: dict = {}

    def counter(name):
        def handler(_sub: str = "") -> None:
            calls[name] = calls.get(name, 0) + 1
        return handler

    handlers = {s: counter(s) for s in STEPS}
    pipeline.run("p3", handlers, scopes={"clips": True})
    first = dict(calls)
    assert first["preprocess"] == 1 and first["transcribe"] == 1

    # 通过 HTTP 接口触发重跑（接口层测试）
    client = TestClient(create_app(pipeline, handlers))
    resp = client.post("/api/ip/projects/p3/jobs/transcribe/retry")
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
    result = pipeline.run("p3b", handlers)
    assert result["status"] == "failed"
    state["fail"] = False
    client = TestClient(create_app(pipeline, handlers))
    resp = client.post("/api/ip/projects/p3b/jobs/transcribe/retry")
    assert resp.status_code == 200
    assert resp.json()["status"] == "succeeded"
    progress = client.get("/api/ip/projects/p3b/jobs").json()
    assert all(j["status"] in ("succeeded", "skipped") for j in progress["jobs"])


def test_ac3c_retry_unknown_step_returns_404():
    pipeline, _ = make_pipeline()
    handlers = {s: (lambda s="": None) for s in STEPS}
    pipeline.run("p3c", handlers)
    client = TestClient(create_app(pipeline, handlers))
    assert client.post("/api/ip/projects/p3c/jobs/nope/retry").status_code == 404


# ---------------------------------------------------------------- AC4
def test_ac4_concurrent_trigger_returns_409():
    """验收 4：同一项目并发触发两次，第二次返回 409。"""
    pipeline, _ = make_pipeline()
    handlers = {s: (lambda s="": None) for s in STEPS}
    # 模拟另一 worker 已持有锁（与 Pipeline.run 内同一把 Redis NX 锁）
    assert pipeline.redis.set("ip:lock:p4", "worker-2", nx=True, ex=7200)
    client = TestClient(create_app(pipeline, handlers))
    resp = client.post("/api/ip/projects/p4/jobs", json={"scopes": {"clips": True}})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "PIPELINE_ALREADY_RUNNING"
    # 走编排器直调同样抛 AlreadyRunning
    with pytest.raises(AlreadyRunning):
        pipeline.run("p4", handlers)


def test_ac4b_pipeline_run_releases_lock_after_finish():
    pipeline, _ = make_pipeline()
    handlers = {s: (lambda s="": None) for s in STEPS}
    pipeline.run("p4b", handlers)
    # 锁已释放：立即再触发成功（不 409）
    client = TestClient(create_app(pipeline, handlers))
    resp = client.post("/api/ip/projects/p4b/jobs", json={"scopes": {"clips": True}})
    assert resp.status_code == 202


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
    tables = set(inspect(engine).get_table_names())
    assert {"ip_project", "ip_jobs", "alembic_version"} <= tables
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
            "started_at", "finished_at", "error_code"} <= cols
