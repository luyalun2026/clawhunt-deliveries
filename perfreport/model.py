"""统一结果模型：把 k6 / Locust / 自采负载样本归一成同一结构。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


def percentile(sorted_vals: List[float], q: float) -> float:
    """线性插值分位数（与 k6 p(n) 的插值口径一致，q 取 0–100）。"""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    pos = (len(sorted_vals) - 1) * (q / 100.0)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return float(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac)


def stats_from_samples(samples: List[float], failed: int = 0) -> Dict[str, float]:
    s = sorted(samples)
    n = len(s)
    return {
        "count": n,
        "failed": failed,
        "p50": percentile(s, 50),
        "p95": percentile(s, 95),
        "p99": percentile(s, 99),
        "avg": (sum(s) / n) if n else 0.0,
        "min": s[0] if n else 0.0,
        "max": s[-1] if n else 0.0,
        "error_rate": (failed / n) if n else 0.0,
    }


@dataclass
class Endpoint:
    name: str
    count: int = 0
    failed: int = 0
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    avg: float = 0.0
    rps: float = 0.0
    error_rate: float = 0.0

    def as_dict(self) -> Dict[str, float]:
        return {
            "count": self.count,
            "failed": self.failed,
            "p50": round(self.p50, 1),
            "p95": round(self.p95, 1),
            "p99": round(self.p99, 1),
            "avg": round(self.avg, 1),
            "rps": round(self.rps, 2),
            "error_rate": round(self.error_rate, 4),
        }


@dataclass
class RunResult:
    source: str
    scenario: str = ""
    duration_s: float = 0.0
    users: int = 0
    total_requests: int = 0
    total_failed: int = 0
    endpoints: List[Endpoint] = field(default_factory=list)
    timeline: List[Dict[str, float]] = field(default_factory=list)  # [{t, users, rps}]
    meta: Dict[str, str] = field(default_factory=dict)

    @property
    def overall_p95(self) -> float:
        if not self.endpoints:
            return 0.0
        worst = max(self.endpoints, key=lambda e: e.p95)
        return worst.p95

    @property
    def error_rate(self) -> float:
        return (self.total_failed / self.total_requests) if self.total_requests else 0.0

    def endpoint(self, name: str) -> Optional[Endpoint]:
        for e in self.endpoints:
            if e.name == name:
                return e
        return None

    def as_dict(self) -> Dict[str, object]:
        return {
            "source": self.source,
            "scenario": self.scenario,
            "duration_s": self.duration_s,
            "users": self.users,
            "total_requests": self.total_requests,
            "total_failed": self.total_failed,
            "error_rate": round(self.error_rate, 4),
            "endpoints": {e.name: e.as_dict() for e in self.endpoints},
            "meta": self.meta,
        }
