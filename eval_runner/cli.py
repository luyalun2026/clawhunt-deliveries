# -*- coding: utf-8 -*-
"""eval-run 命令行入口。

    python -m eval_runner.cli run --suite mock20 --target mock --concurrency 4
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .adapters import build_adapter
from .core import run_suite

DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "config", "tools.json")


def _load_config(path: str) -> dict:
    if not os.path.exists(path):
        return {"tools": {}}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="eval-run", description="会员空间平台 AI 工具评测执行器")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="执行一个评测套件")
    r.add_argument("--suite", required=True, help="套件标识（mock20 / mock_timeout / JSON 路径）")
    r.add_argument("--target", required=True, help="被测工具名（见 config/tools.json）或 mock")
    r.add_argument("--concurrency", type=int, default=4)
    r.add_argument("--timeout", type=float, default=60.0, dest="timeout_s")
    r.add_argument("--retries", type=int, default=1)
    r.add_argument("--tags", default="", help="逗号分隔，命中任一标签即执行")
    r.add_argument("--case", default="", help="逗号分隔用例 id")
    r.add_argument("--sample", type=int, default=None)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--pass-threshold", type=float, default=0.8, dest="threshold")
    r.add_argument("--resume", default=None, help="run_id：跳过该 run 已完成用例")
    r.add_argument("--db", default="db/eval.sqlite3")
    r.add_argument("--config", default=DEFAULT_CONFIG)
    r.add_argument("--json", action="store_true", help="输出机器可读汇总")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = _load_config(args.config)

    if args.target == "mock":
        adapter = build_adapter({"tools": {"mock": {"adapter": "echo"}}}, "mock")
    else:
        adapter = build_adapter(cfg, args.target, default_timeout_s=args.timeout_s)

    options = {
        "concurrency": args.concurrency,
        "timeout_s": args.timeout_s,
        "retries": args.retries,
        "tags": [t for t in args.tags.split(",") if t.strip()],
        "case_ids": [c for c in args.case.split(",") if c.strip()],
        "sample": args.sample,
        "seed": args.seed,
        "pass_threshold": args.threshold,
        "resume_run_id": args.resume,
        "db_path": args.db,
    }
    summary = run_suite(args.suite, args.target, options=options, adapter=adapter)
    payload = summary.as_dict()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print("[eval-run] run_id=%s target=%s suite=%s" % (summary.run_id, args.target, args.suite))
        print("[eval-run] 用例 %d 条：执行 %d / 跳过 %d；passed=%d failed=%d error=%d"
              % (summary.total, summary.executed, summary.skipped,
                 summary.passed, summary.failed, summary.error))
        print("[eval-run] 通过率 %.2f%% 阈值 %.0f%% 耗时 %d ms 退出码 %d"
              % (summary.pass_rate * 100, args.threshold * 100,
                 summary.duration_ms, summary.exit_code))
    return summary.exit_code


if __name__ == "__main__":
    sys.exit(main())
