# -*- coding: utf-8 -*-
"""自检：跑 pytest + CLI 冒烟，从真实输出里抽取 AC 数字，写 outputs/verify.json 与 ac-checklist.csv。

所有交付文档/载荷里的数字都来自本脚本的抽取结果，禁止手工填写。
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")


def run(cmd: list[str], extra_env: dict | None = None) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = HERE
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if extra_env:
        env.update(extra_env)
    p = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=900)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    ok = True

    junit = os.path.join(OUT, "junit.xml")
    rc_pt, pt = run([sys.executable, "-m", "pytest", "-q", "-s", "--junitxml=" + junit, "tests"])
    open(os.path.join(OUT, "pytest.txt"), "w", encoding="utf-8").write(
        "$ python -m pytest -q -s tests\n" + pt + "\nexit=%d\n" % rc_pt)
    passed_tests, failed_tests = 0, 0
    if os.path.exists(junit):
        xml = open(junit, "r", encoding="utf-8", errors="replace").read()
        suite_tag = re.search(r"<testsuite\b[^>]*>", xml)
        if suite_tag:
            tag = suite_tag.group(0)
            n = re.search(r'tests="(\d+)"', tag)
            f = re.search(r'failures="(\d+)"', tag)
            e = re.search(r'errors="(\d+)"', tag)
            total = int(n.group(1)) if n else 0
            failed_tests = (int(f.group(1)) if f else 0) + (int(e.group(1)) if e else 0)
            passed_tests = total - failed_tests
    if passed_tests == 0:  # 兜底：从进度点计数
        passed_tests = pt.count(".")
    if rc_pt != 0 or passed_tests < 8 or failed_tests != 0:
        ok = False

    ac1 = re.search(r"\[AC1\] serial=(\d+)ms\s+concurrency4=(\d+)ms\s+speedup=([\d.]+)x", pt)
    ac2 = re.search(r"\[AC2\] exit_code=(\d+) error=(\d+) attempts\(SLOW-01\)=(\d+)", pt)
    ac3 = re.search(r"\[AC3\] run_id=(\S+) 首轮=(\d+) 续跑=(\d+) 跳过=(\d+) 结果行=(\d+) "
                    r"去重后=(\d+) 第二轮调用=(\d+)", pt)
    ac4 = re.search(r"\[AC4\] passed=(\d+) failed=(\d+) error=(\d+) pass_rate=([\d.]+) "
                    r"exit_code=(\d+)", pt)
    if not all([ac1, ac2, ac3, ac4]):
        ok = False

    rc_cli, cli = run([sys.executable, "-m", "eval_runner.cli", "run", "--suite", "mock20",
                       "--target", "mock", "--concurrency", "4", "--db", "outputs/cli.sqlite3"])
    rc_thr, thr = run([sys.executable, "-m", "eval_runner.cli", "run", "--suite", "mock20",
                       "--target", "mock", "--concurrency", "4", "--pass-threshold", "1.1",
                       "--db", "outputs/cli_thr.sqlite3"])
    open(os.path.join(OUT, "cli-run.txt"), "w", encoding="utf-8").write(
        "$ python -m eval_runner.cli run --suite mock20 --target mock --concurrency 4\n"
        + cli + "\nexit_code=%d\n\n" % rc_cli
        + "$ ... --pass-threshold 1.1   # 阈值不可达，验证退出码 3\n"
        + thr + "\nexit_code=%d\n" % rc_thr)

    cli_ms = re.search(r"耗时 (\d+) ms 退出码 (\d+)", cli)
    thr_ms = re.search(r"耗时 (\d+) ms 退出码 (\d+)", thr)

    verify = {
        "problem_id": 1987,
        "suite": "mock20",
        "pytest": {"exit": rc_pt, "passed": passed_tests},
        "ac1": {"serial_ms": int(ac1.group(1)) if ac1 else None,
                "concurrency4_ms": int(ac1.group(2)) if ac1 else None,
                "speedup": float(ac1.group(3)) if ac1 else None},
        "ac2": {"exit_code": int(ac2.group(1)) if ac2 else None,
                "error": int(ac2.group(2)) if ac2 else None,
                "attempts": int(ac2.group(3)) if ac2 else None},
        "ac3": {"run_id": ac3.group(1) if ac3 else None,
                "first_executed": int(ac3.group(2)) if ac3 else None,
                "resume_executed": int(ac3.group(3)) if ac3 else None,
                "skipped": int(ac3.group(4)) if ac3 else None,
                "rows": int(ac3.group(5)) if ac3 else None,
                "distinct": int(ac3.group(6)) if ac3 else None,
                "second_wave_calls": int(ac3.group(7)) if ac3 else None},
        "ac4": {"passed": int(ac4.group(1)) if ac4 else None,
                "failed": int(ac4.group(2)) if ac4 else None,
                "error": int(ac4.group(3)) if ac4 else None,
                "pass_rate": float(ac4.group(4)) if ac4 else None,
                "exit_code": int(ac4.group(5)) if ac4 else None},
        "cli": {"exit": rc_cli, "duration_ms": int(cli_ms.group(1)) if cli_ms else None,
                "exit_code": int(cli_ms.group(2)) if cli_ms else None,
                "threshold_exit": rc_thr,
                "threshold_exit_code": int(thr_ms.group(2)) if thr_ms else None},
    }

    checks = [
        ("pytest 全通过（8 例）", rc_pt == 0 and passed_tests == 8),
        ("AC1 加速比 2.0~8.0 且 20 例全过", bool(ac1) and 2.0 <= float(ac1.group(3)) <= 8.0),
        ("AC2 超时重试 1 次（attempts=2）且退出码 2",
         bool(ac2) and ac2.group(3) == "2" and ac2.group(1) == "2"),
        ("AC3 续跑只执行剩余 12 条、结果 20 行无重复",
         bool(ac3) and ac3.group(3) == "12" and ac3.group(5) == "20" and ac3.group(6) == "20"),
        ("AC4 通过率 0.50 低于阈值 → 退出码 3",
         bool(ac4) and ac4.group(4) == "0.50" and ac4.group(5) == "3"),
        ("CLI 默认场景退出码 0", rc_cli == 0 and cli_ms and cli_ms.group(2) == "0"),
        ("CLI 阈值不可达场景退出码 3", rc_thr == 3 and thr_ms and thr_ms.group(2) == "3"),
    ]
    verify["checks"] = [{"name": n, "ok": bool(v)} for n, v in checks]
    verify["all_ok"] = all(v for _, v in checks)
    ok = ok and verify["all_ok"]

    with open(os.path.join(OUT, "verify.json"), "w", encoding="utf-8") as fh:
        json.dump(verify, fh, ensure_ascii=False, indent=2)

    with open(os.path.join(OUT, "ac-checklist.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["AC", "要求", "实现位置", "测试", "实测", "结论"])
        w.writerow(["1", "20 条 mock 用例 --concurrency 4 总耗时约为串行 1/4",
                    "core.run_suite 线程池", "test_ac1_concurrency_speedup_is_about_4x",
                    "串行 %s ms / 并发 %s ms = %sx" % (verify["ac1"]["serial_ms"],
                                                     verify["ac1"]["concurrency4_ms"],
                                                     verify["ac1"]["speedup"]),
                    "通过" if checks[1][1] else "不通过"])
        w.writerow(["2", "超时用例重试 1 次后记 error，退出码 2", "core._execute_case",
                    "test_ac2_timeout_retry_once_then_error_exit_2",
                    "attempts=%s exit_code=%s" % (verify["ac2"]["attempts"], verify["ac2"]["exit_code"]),
                    "通过" if checks[2][1] else "不通过"])
        w.writerow(["3", "--resume 只执行剩余用例，结果表无重复", "store.completed_case_ids",
                    "test_ac3_resume_runs_only_remaining_cases",
                    "首轮 %s / 续跑 %s / 结果行 %s / 去重 %s" % (
                        verify["ac3"]["first_executed"], verify["ac3"]["resume_executed"],
                        verify["ac3"]["rows"], verify["ac3"]["distinct"]),
                    "通过" if checks[3][1] else "不通过"])
        w.writerow(["4", "通过率低于阈值时退出码 3", "run_suite 退出码判定",
                    "test_ac4_below_threshold_exit_3",
                    "pass_rate=%s exit_code=%s" % (verify["ac4"]["pass_rate"],
                                                   verify["ac4"]["exit_code"]),
                    "通过" if checks[4][1] else "不通过"])

    for name, good in checks:
        print(("  [OK] " if good else "  [FAIL] ") + name)
    print("all_ok =", verify["all_ok"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
