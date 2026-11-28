# -*- coding: utf-8 -*-
"""判定器配置：阈值与时效全部从环境变量读取，缺省值在此集中声明。"""
import os
from dataclasses import dataclass

DEFAULTS = {
    "KB_MIN_RERANK_SCORE": 0.35,
    "KB_MIN_EVIDENCE": 1,
    "DOC_FRESHNESS_DAYS": 180,
    "KB_GAP_BASE_URL": "http://stub.local/api/kb/gaps",
}


@dataclass(frozen=True)
class Settings:
    min_rerank_score: float = 0.35
    min_evidence: int = 1
    doc_freshness_days: int = 180
    gap_base_url: str = DEFAULTS["KB_GAP_BASE_URL"]
    used_defaults: tuple = ()

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        used = []
        vals = {}
        for key, dv in DEFAULTS.items():
            raw = env.get(key)
            if raw is None or str(raw).strip() == "":
                vals[key] = dv
                used.append(key)
            else:
                vals[key] = float(raw) if isinstance(dv, float) else int(raw)
        return cls(
            min_rerank_score=vals["KB_MIN_RERANK_SCORE"],
            min_evidence=vals["KB_MIN_EVIDENCE"],
            doc_freshness_days=vals["DOC_FRESHNESS_DAYS"],
            gap_base_url=str(vals["KB_GAP_BASE_URL"]),
            used_defaults=tuple(used),
        )
