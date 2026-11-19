# -*- coding: utf-8 -*-
"""验收标准（AC）逐条测试。每条 AC 对应一个测试函数，断言直接对应 AC 原文。"""
from __future__ import annotations

import time

from eval_runner import Case, EchoMockAdapter, run_suite
from eval_runner.suites import mock_cases


def _db(tmp_path, name="eval.sqlite3") -> str:
    return str(tmp_path / name)


# AC1：对 20 条用例的 mock 套件，--concurrency 4 时总耗时约为串行的 1/4（测试输出）
def test_ac1_concurrency_speedup_is_about_4x(tmp_path):
    cases = mock_cases(20, sleep_s=0.05)

    serial = run_suite("mock20", EchoMockAdapter(), options={
        "concurrency": 1, "db_path": _db(tmp_path, "serial.db"), "timeout_s": 5,
    }, cases=cases)

    concurrent = run_suite("mock20", EchoMockAdapter(), options={
        "concurrency": 4, "db_path": _db(tmp_path, "conc.db"), "timeout_s": 5,
    }, cases=cases)

    print("\n[AC1] serial=%dms  concurrency4=%dms  speedup=%.2fx"
          % (serial.duration_ms, concurrent.duration_ms,
             serial.duration_ms / max(1, concurrent.duration_ms)))

    assert serial.passed == 20 and concurrent.passed == 20
    assert serial.duration_ms > 800, "串行 20x50ms 应 >800ms，实测 %d" % serial.duration_ms
    speedup = serial.duration_ms / max(1, concurrent.duration_ms)
    assert 2.0 <= speedup <= 8.0, "并发 4 的加速比应接近 4x，实测 %.2fx" % speedup


# AC2：模拟超时的用例重试 1 次后记为 error，运行退出码为 2
def test_ac2_timeout_retry_once_then_error_exit_2(tmp_path):
    cases = [Case(case_id="OK-%02d" % i, input={"behavior": "ok"}, expected={"seq": 0})
             for i in range(1, 4)]
    cases.append(Case(case_id="SLOW-01", input={"behavior": "timeout"}))

    summary = run_suite("mock_timeout", EchoMockAdapter(), options={
        "concurrency": 2, "timeout_s": 0.10, "retries": 1, "db_path": _db(tmp_path),
    }, cases=cases)

    rows = {r["case_id"]: r for r in _fetch_rows(tmp_path)}
    print("\n[AC2] exit_code=%d error=%d attempts(SLOW-01)=%d"
          % (summary.exit_code, summary.error, rows["SLOW-01"]["attempts"]))

    assert summary.error == 1
    assert rows["SLOW-01"]["status"] == "error"
    assert rows["SLOW-01"]["attempts"] == 2, "超时后应重试 1 次，共 2 次尝试"
    assert summary.exit_code == 2


# AC3：运行到一半中断后 --resume 只执行剩余用例（结果表无重复，测试断言）
def test_ac3_resume_runs_only_remaining_cases(tmp_path):
    cases = mock_cases(20)
    first_ids = [c.case_id for c in cases[:8]]

    adapter = EchoMockAdapter()
    first = run_suite("mock20", adapter, options={
        "concurrency": 2, "case_ids": first_ids, "db_path": _db(tmp_path), "timeout_s": 5,
    }, cases=cases)
    assert first.executed == 8

    calls_after_first = len(adapter.calls)
    resumed = run_suite("mock20", adapter, options={
        "concurrency": 2, "resume_run_id": first.run_id, "db_path": _db(tmp_path), "timeout_s": 5,
    }, cases=cases)

    second_wave = adapter.calls[calls_after_first:]
    rows = _fetch_rows(tmp_path)
    case_ids = [r["case_id"] for r in rows]

    print("\n[AC3] run_id=%s 首轮=%d 续跑=%d 跳过=%d 结果行=%d 去重后=%d 第二轮调用=%d"
          % (first.run_id, first.executed, resumed.executed, resumed.skipped,
             len(rows), len(set(case_ids)), len(second_wave)))

    assert resumed.run_id == first.run_id
    assert resumed.executed == 12, "续跑应只执行剩余 12 条"
    assert resumed.skipped == 8
    assert len(rows) == 20, "结果表应为 20 行"
    assert len(set(case_ids)) == 20, "结果表不得有重复 case_id"
    assert not (set(first_ids) & set(second_wave)), "续跑不得重复执行已完成用例"
    assert sorted(case_ids) == sorted(c.case_id for c in cases)


# AC4：通过率低于阈值时退出码为 3（pytest 通过）
def test_ac4_below_threshold_exit_3(tmp_path):
    cases = []
    for i in range(1, 11):
        behavior = "fail" if i <= 5 else "ok"
        cases.append(Case(case_id="TH-%02d" % i, input={"behavior": behavior}, expected={"seq": 0}))

    summary = run_suite("thr", EchoMockAdapter(), options={
        "concurrency": 2, "pass_threshold": 0.9, "db_path": _db(tmp_path), "timeout_s": 5,
    }, cases=cases)

    print("\n[AC4] passed=%d failed=%d error=%d pass_rate=%.2f exit_code=%d"
          % (summary.passed, summary.failed, summary.error, summary.pass_rate, summary.exit_code))

    assert summary.error == 0, "本用例不应出现执行错误（否则退出码会是 2）"
    assert summary.pass_rate == 0.5
    assert summary.exit_code == 3


def _fetch_rows(tmp_path):
    from eval_runner.store import Store
    st = Store(_db(tmp_path))
    try:
        row = st.conn.execute("SELECT id FROM eval_run ORDER BY created_at LIMIT 1").fetchone()
        return st.results_for_run(row["id"])
    finally:
        st.close()
