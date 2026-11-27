"""Locust CSV 结果解析。

读取 `--csv=prefix` 产生的：
- prefix_stats.csv（按请求名聚合，含 50%/95%/99% 列与 Aggregated 行）
- prefix_stats_history.csv（时间序列，含 User Count 与 Requests/s，用于并发曲线）
- prefix_failures.csv（可选，失败明细）
"""
from __future__ import annotations

import csv
from typing import Dict, List

from .model import Endpoint, RunResult


def _f(row: Dict[str, str], key: str, default: float = 0.0) -> float:
    v = row.get(key)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


def parse_locust_csv(stats_path: str, history_path: str | None = None,
                     scenario: str = "") -> RunResult:
    rows = list(csv.DictReader(open(stats_path, encoding="utf-8-sig")))
    eps: List[Endpoint] = []
    total = failed = 0
    duration = 0.0
    for row in rows:
        name = (row.get("Name") or "").strip()
        if not name or name == "Aggregated":
            if name == "Aggregated":
                total = int(_f(row, "Request Count"))
                failed = int(_f(row, "Failure Count"))
            continue
        rps = _f(row, "Requests/s")
        eps.append(Endpoint(
            name=f"{row.get('Type','')} {name}".strip(),
            count=int(_f(row, "Request Count")),
            failed=int(_f(row, "Failure Count")),
            p50=_f(row, "50%") or _f(row, "Median Response Time"),
            p95=_f(row, "95%"),
            p99=_f(row, "99%"),
            avg=_f(row, "Average Response Time"),
            rps=rps,
            error_rate=(_f(row, "Failure Count") / max(_f(row, "Request Count"), 1)),
        ))
    if not total:
        total = sum(e.count for e in eps)
        failed = sum(e.failed for e in eps)

    timeline: List[Dict[str, float]] = []
    users = 0
    if history_path:
        hrows = list(csv.DictReader(open(history_path, encoding="utf-8-sig")))
        agg: Dict[str, Dict[str, float]] = {}
        for row in hrows:
            ts = row.get("Timestamp") or ""
            users = max(users, int(_f(row, "User Count", users)))
            if (row.get("Name") or "") == "Aggregated":
                agg[ts] = {"t": 0.0, "users": users, "rps": _f(row, "Requests/s")}
            if ts:
                duration = max(duration, 1.0)
        # 时间轴改为相对秒
        keys = sorted(agg)
        for i, ts in enumerate(keys):
            point = agg[ts]
            timeline.append({"t": float(i), "users": point["users"], "rps": point["rps"]})
        if keys:
            duration = float(len(keys))

    eps.sort(key=lambda e: e.name)
    r = RunResult(source="locust-csv", scenario=scenario, endpoints=eps, total_requests=total,
                  total_failed=failed, timeline=timeline, users=users, duration_s=duration)
    return r


def read_failures(path: str) -> List[Dict[str, str]]:
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    out = []
    for r in rows:
        if (r.get("Name") or "") == "Aggregated":
            continue
        out.append({"method": r.get("Method", ""), "name": r.get("Name", ""),
                    "error": (r.get("Error") or "")[:200], "occurrences": r.get("Occurrences", "")})
    return out
