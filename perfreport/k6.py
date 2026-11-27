"""k6 结果解析。

支持两种官方输出：
1) `k6 run --out json=result.json`（JSON Lines，每个样本一行；按 data.tags.name 分组，可算端点分位）
2) `k6 run --summary-export=summary.json`（仅全局聚合，无端点点位；用作回退）
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Dict, List

from .model import Endpoint, RunResult, stats_from_samples


def parse_k6_jsonl(path: str) -> RunResult:
    dur: Dict[str, List[float]] = defaultdict(list)
    failed: Dict[str, int] = defaultdict(int)
    total_dur: List[float] = []
    total_failed = 0
    total = 0
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("type") != "Point":
            continue
        m = (rec.get("metric") or "")
        d = rec.get("data") or {}
        tags = d.get("tags") or {}
        name = tags.get("name") or tags.get("url") or "（未命名）"
        val = d.get("value")
        if val is None:
            continue
        if m == "http_req_duration":
            v = float(val)
            dur[name].append(v)
            total_dur.append(v)
            total += 1
        elif m == "http_req_failed":
            if float(val) >= 1:
                failed[name] += 1
                total_failed += 1
    eps = []
    for name, samples in dur.items():
        st = stats_from_samples(samples, failed[name])
        eps.append(Endpoint(name=name, count=st["count"], failed=st["failed"], p50=st["p50"],
                            p95=st["p95"], p99=st["p99"], avg=st["avg"], error_rate=st["error_rate"]))
    eps.sort(key=lambda e: e.name)
    r = RunResult(source="k6-jsonl", endpoints=eps, total_requests=total, total_failed=total_failed)
    if total_dur:
        st = stats_from_samples(total_dur, total_failed)
        r.meta["global_p95"] = f"{st['p95']:.1f}"
    return r


def _vals(metric: dict) -> dict:
    """兼容 k6 summary-export 两种版本：旧版 metric={"values":{...}}，v2.x 扁平。"""
    v = metric.get("values")
    return v if isinstance(v, dict) else metric


def parse_k6_summary(path: str) -> RunResult:
    doc = json.load(open(path, encoding="utf-8"))
    metrics = doc.get("metrics") or {}
    d = _vals(metrics.get("http_req_duration") or {})
    reqs = _vals(metrics.get("http_reqs") or {})
    failed = _vals(metrics.get("http_req_failed") or {})
    count = int(reqs.get("count") or 0)
    # k6 版本差异：旧版失败率在 rate，v2.x 在 value（另含 passes/fails 计数）
    rate = failed.get("rate") if failed.get("rate") is not None else failed.get("value")
    err = float(rate or 0.0)
    ep = Endpoint(
        name="（全局聚合）",
        count=count,
        failed=int(round(count * err)),
        p50=float(d.get("med") or 0.0),
        p95=float(d.get("p(95)") or d.get("p(90)") or 0.0),
        p99=float(d.get("p(99)") or d.get("p(95)") or 0.0),
        avg=float(d.get("avg") or 0.0),
        error_rate=err,
    )
    r = RunResult(source="k6-summary", endpoints=[ep], total_requests=count,
                  total_failed=ep.failed)
    r.meta["note"] = "summary-export 只有全局聚合，端点级 P50/P95/P99 需 --out json 的 JSONL"
    return r
