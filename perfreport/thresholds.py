"""阈值与上一轮对比。"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from .model import RunResult

DEFAULT = {"global": {"p50_ms": 200.0, "p95_ms": 500.0, "p99_ms": 1000.0, "error_rate": 0.01}, "endpoints": {}}


def load_thresholds(path: Optional[str]) -> Dict:
    if not path:
        return json.loads(json.dumps(DEFAULT))
    doc = json.load(open(path, encoding="utf-8"))
    out = json.loads(json.dumps(DEFAULT))
    out["global"].update(doc.get("global") or {})
    out["endpoints"] = doc.get("endpoints") or {}
    return out


def _pick(name: str, thr: Dict, metric: str) -> Optional[float]:
    ep = thr["endpoints"].get(name)
    if isinstance(ep, dict) and metric in ep:
        return float(ep[metric])
    if metric in thr["global"]:
        return float(thr["global"][metric])
    return None


METRICS = [("p50", "p50_ms"), ("p95", "p95_ms"), ("error_rate", "error_rate")]


def compare(run: RunResult, thr: Dict, prev: Optional[RunResult] = None) -> List[Dict]:
    checks: List[Dict] = []
    for ep in run.endpoints:
        for attr, key in METRICS:
            limit = _pick(ep.name, thr, key)
            if limit is None:
                continue
            actual = getattr(ep, attr)
            prev_val = None
            if prev is not None:
                pep = prev.endpoint(ep.name)
                if pep is not None:
                    prev_val = getattr(pep, attr)
            delta = None
            if prev_val not in (None, 0):
                delta = (actual - prev_val) / prev_val * 100.0
            checks.append({
                "scope": ep.name,
                "metric": attr,
                "actual": round(actual, 2),
                "threshold": round(limit, 2),
                "ok": actual <= limit,
                "prev": None if prev_val is None else round(prev_val, 2),
                "delta_pct": None if delta is None else round(delta, 1),
            })
    return checks


def overall(checks: List[Dict]) -> Dict[str, object]:
    failed = [c for c in checks if not c["ok"]]
    regressions = [c for c in checks if c["delta_pct"] is not None and c["delta_pct"] > 10]
    return {
        "total": len(checks),
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "verdict": "PASS" if not failed else "FAIL",
        "failed_items": failed,
        "regressions": regressions,
    }
