# -*- coding: utf-8 -*-
"""判定器配置：阈值与时效全部从环境变量读取，缺省值在此集中声明。"""
import os
from dataclasses import dataclass
from urllib.parse import urlparse

DEFAULTS = {
    "KB_MIN_RERANK_SCORE": 0.35,
    "KB_MIN_EVIDENCE": 1,
    "DOC_FRESHNESS_DAYS": 180,
    "KB_GAP_BASE_URL": "http://stub.local/api/kb/gaps",
}


def validate_gap_url(raw):
    """缺口服务地址必须为 http/https 且含合法主机名，防止误配导致数据外传。"""
    u = urlparse(str(raw))
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError(
            "KB_GAP_BASE_URL 必须为 http/https 且含主机名，当前值不合法：%r" % (raw,))
    return str(raw)


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
            elif key == "KB_GAP_BASE_URL":
                vals[key] = validate_gap_url(raw)
            else:
                vals[key] = float(raw) if isinstance(dv, float) else int(raw)
        return cls(
            min_rerank_score=vals["KB_MIN_RERANK_SCORE"],
            min_evidence=vals["KB_MIN_EVIDENCE"],
            doc_freshness_days=vals["DOC_FRESHNESS_DAYS"],
            gap_base_url=str(vals["KB_GAP_BASE_URL"]),
            used_defaults=tuple(used),
        )
