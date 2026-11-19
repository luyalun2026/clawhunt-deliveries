# -*- coding: utf-8 -*-
"""评测执行器核心：并发执行、超时重试、断点续跑、退出码。

退出码约定（供 CI 判断）：
    0  全部用例执行完成且通过率达阈值
    2  存在执行错误（含超时重试后仍失败）
    3  无执行错误但通过率低于 pass_threshold
"""
from __future__ import annotations

import json
import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .store import Store

EXIT_OK = 0
EXIT_CASE_ERROR = 2
EXIT_BELOW_THRESHOLD = 3


@dataclass
class Case:
    case_id: str
    tags: list[str] = field(default_factory=list)
    input: dict = field(default_factory=dict)
    expected: dict = field(default_factory=dict)


@dataclass
class CaseResult:
    case_id: str
    status: str  # passed | failed | error
    latency_ms: int
    attempts: int
    tokens_in: int = 0
    tokens_out: int = 0
    error: str | None = None
    output: dict | None = None


@dataclass
class RunSummary:
    run_id: str
    exit_code: int
    total: int
    executed: int
    skipped: int
    passed: int
    failed: int
    error: int
    pass_rate: float
    duration_ms: int

    def as_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "exit_code": self.exit_code,
            "total": self.total,
            "executed": self.executed,
            "skipped": self.skipped,
            "passed": self.passed,
            "failed": self.failed,
            "error": self.error,
            "pass_rate": round(self.pass_rate, 4),
            "duration_ms": self.duration_ms,
        }


def _execute_case(adapter, case: Case, timeout_s: float, retries: int) -> CaseResult:
    attempts = 0
    last_err: str | None = None
    t0 = time.perf_counter()
    while attempts <= retries:
        attempts += 1
        try:
            out = adapter.invoke(case, timeout_s)
            latency = int((time.perf_counter() - t0) * 1000)
            ok = adapter.judge(case, out)
            return CaseResult(
                case_id=case.case_id,
                status="passed" if ok else "failed",
                latency_ms=latency,
                attempts=attempts,
                tokens_in=int(out.get("tokens_in", 0) or 0),
                tokens_out=int(out.get("tokens_out", 0) or 0),
                error=None if ok else str(out.get("reason", "assertion failed")),
                output=out,
            )
        except Exception as exc:  # noqa: BLE001  超时/网络/协议错误统一记为执行错误
            last_err = "%s: %s" % (type(exc).__name__, exc)
    latency = int((time.perf_counter() - t0) * 1000)
    return CaseResult(
        case_id=case.case_id,
        status="error",
        latency_ms=latency,
        attempts=attempts,
        error=last_err,
    )


def _select_cases(cases: list[Case], options: dict) -> list[Case]:
    tags = options.get("tags") or []
    only_ids = options.get("case_ids") or []
    selected = list(cases)
    if tags:
        want = set(tags)
        selected = [c for c in selected if want & set(c.tags)]
    if only_ids:
        keep = set(only_ids)
        selected = [c for c in selected if c.case_id in keep]
    return selected


def _sample(cases: list[Case], n: int | None, seed: int) -> list[Case]:
    if not n or n >= len(cases):
        return cases
    rng = random.Random(seed)  # 固定种子：同样本可复现
    picked = rng.sample(range(len(cases)), n)
    return [cases[i] for i in sorted(picked)]


def run_suite(suite_key: str, target, options: dict | None = None,
              adapter=None, cases: list[Case] | None = None) -> RunSummary:
    """Python API 入口。target 为工具名（配合 adapter）或直接传 adapter 实例。"""
    options = dict(options or {})
    concurrency = int(options.get("concurrency", 4) or 1)
    timeout_s = float(options.get("timeout_s", 60.0))
    retries = int(options.get("retries", 1))
    threshold = float(options.get("pass_threshold", 0.8))
    db_path = options.get("db_path", "db/eval.sqlite3")
    org_id = options.get("org_id", "00000000-0000-0000-0000-000000000001")
    site_id = options.get("site_id", "00000000-0000-0000-0000-000000000002")
    created_by = options.get("created_by", "eval-runner")

    adapter = adapter if adapter is not None else target
    if not hasattr(adapter, "invoke"):
        raise TypeError("run_suite 需要适配器实例（build_adapter 的返回值）")

    if cases is None:
        from .suites import load_suite
        cases = load_suite(suite_key)

    selected = _sample(_select_cases(cases, options), options.get("sample"), int(options.get("seed", 0)))

    store = Store(db_path)
    try:
        resume_id = options.get("resume_run_id")
        if resume_id:
            run_id = resume_id
            done = store.completed_case_ids(run_id)
            todo = [c for c in selected if c.case_id not in done]
            store.mark_run_status(run_id, "running")
        else:
            run_id = str(uuid.uuid4())
            done = set()
            todo = selected
            store.create_run(run_id, org_id=org_id, site_id=site_id, suite_key=suite_key,
                             target=getattr(adapter, "name", str(target)),
                             options=options, created_by=created_by)

        started = time.perf_counter()
        results: list[CaseResult] = []
        if todo:
            with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
                futures = [pool.submit(_execute_case, adapter, c, timeout_s, retries) for c in todo]
                for fut in futures:
                    res = fut.result()
                    results.append(res)
                    store.add_result(run_id, res, org_id=org_id, site_id=site_id)

        duration_ms = int((time.perf_counter() - started) * 1000)

        all_rows = store.results_for_run(run_id)
        passed = sum(1 for r in all_rows if r["status"] == "passed")
        failed = sum(1 for r in all_rows if r["status"] == "failed")
        errors = sum(1 for r in all_rows if r["status"] == "error")
        executed_rows = len(all_rows)
        pass_rate = (passed / executed_rows) if executed_rows else 0.0

        if errors > 0:
            exit_code = EXIT_CASE_ERROR
        elif pass_rate < threshold:
            exit_code = EXIT_BELOW_THRESHOLD
        else:
            exit_code = EXIT_OK

        store.finish_run(run_id, exit_code=exit_code, pass_rate=pass_rate,
                         total=executed_rows, duration_ms=duration_ms)
        return RunSummary(
            run_id=run_id,
            exit_code=exit_code,
            total=len(selected),
            executed=len(results),
            skipped=len(selected) - len(todo),
            passed=passed,
            failed=failed,
            error=errors,
            pass_rate=pass_rate,
            duration_ms=duration_ms,
        )
    finally:
        store.close()
