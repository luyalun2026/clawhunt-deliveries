"""命令行入口：

python -m perfreport.cli --locust samples/locust/run --thresholds thresholds.json \
       --previous samples/previous/prev.json --env env.json --scenario "混合读写" -o report.html
python -m perfreport.cli --k6-jsonl out.json --k6-summary summary.json ...
"""
from __future__ import annotations

import argparse
import json
import os

from . import k6, locust, render, thresholds
from .model import RunResult


def _load_prev(path: str | None) -> RunResult | None:
    if not path:
        return None
    doc = json.load(open(path, encoding="utf-8"))
    if "run" in doc:  # 本工具 --json-out 的完整结构
        doc = doc["run"]
    from .model import Endpoint
    eps = [Endpoint(name=n, **{k: v for k, v in d.items()}) for n, d in doc["endpoints"].items()]
    return RunResult(source=doc.get("source", "previous"), scenario=doc.get("scenario", ""),
                     endpoints=eps, total_requests=doc.get("total_requests", 0),
                     total_failed=doc.get("total_failed", 0), users=doc.get("users", 0))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="k6 / Locust 结果 → 单文件 HTML 性能报告")
    ap.add_argument("--locust", help="Locust CSV 前缀（不含 _stats.csv）")
    ap.add_argument("--k6-jsonl", help="k6 --out json 结果文件（JSONL）")
    ap.add_argument("--k6-summary", help="k6 --summary-export 结果文件")
    ap.add_argument("--thresholds", help="阈值 JSON")
    ap.add_argument("--previous", help="上一轮 summary JSON（由 --json-out 产生）")
    ap.add_argument("--env", help="环境信息 JSON（键值对，渲染为表格）")
    ap.add_argument("--scenario", default="", help="场景描述")
    ap.add_argument("--title", default="性能测试报告")
    ap.add_argument("--purpose", default="")
    ap.add_argument("-o", "--output", default="report.html")
    ap.add_argument("--json-out", default=None, help="同时输出机器可读汇总 JSON（供下一轮做基线）")
    args = ap.parse_args(argv)

    if args.locust:
        stats = args.locust + "_stats.csv"
        hist = args.locust + "_stats_history.csv"
        run = locust.parse_locust_csv(stats, hist if os.path.exists(hist) else None, args.scenario)
    elif args.k6_jsonl:
        run = k6.parse_k6_jsonl(args.k6_jsonl)
        run.scenario = args.scenario
    elif args.k6_summary:
        run = k6.parse_k6_summary(args.k6_summary)
        run.scenario = args.scenario
    else:
        ap.error("需要 --locust / --k6-jsonl / --k6-summary 之一")

    thr = thresholds.load_thresholds(args.thresholds)
    prev = _load_prev(args.previous)
    checks = thresholds.compare(run, thr, prev)
    summary = thresholds.overall(checks)
    env = json.load(open(args.env, encoding="utf-8")) if args.env else {}

    html = render.build_html(run, checks, summary, prev=prev, title=args.title,
                             environment=env, purpose=args.purpose)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    doc = {"run": run.as_dict(), "checks": checks, "summary": summary}
    if args.json_out:
        json.dump(doc, open(args.json_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"report -> {args.output} ({len(html)} bytes) | verdict={summary['verdict']} "
          f"| checks={summary['total']} failed={summary['failed']}")
    return 0 if summary["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
