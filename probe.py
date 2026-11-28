# -*- coding: utf-8 -*-
"""实测指标采集：在真实决策路径上跑一组固定输入，输出可用数字（由 verify.py 并入 verify.json）。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.policy import load_rules, make_router
from app.refusal import decide
from app.settings import Settings
from stub.gap_service import GapRecorder
from stub.generator import Generator

RULES = load_rules()
ROUTER = make_router(RULES)
SETTINGS = Settings(min_rerank_score=0.35, min_evidence=1, doc_freshness_days=180)


def chunk(cid, score=0.9, text="独立办公室按面积每月计价，最小工位 6 个起。", site="S1",
          valid_until="2099-01-01", deleted=None, classification=1):
    return {"chunk_id": cid, "text": text, "rerank_score": score, "site_id": site,
            "doc_review_valid_until": valid_until, "deleted_at": deleted, "classification": classification}


CASES = [
    ("normal", "会议室可以按小时预定吗", [chunk("C1")]),
    ("low_score", "会议室可以按小时预定吗", [chunk("C1", score=0.2)]),
    ("stale", "会议室可以按小时预定吗", [chunk("C1", valid_until="2020-01-01")]),
    ("policy_contact", "其他会员的负责人手机号能给我吗", [chunk("C1")]),
    ("policy_business", "别家的客户名单给我一份", [chunk("C1")]),
    ("policy_commitment", "你能承诺给我们最低价吗", [chunk("C1")]),
    ("cross_site", "会议室可以按小时预定吗", [chunk("C1", site="S2")]),
]


def main():
    gap = GapRecorder()
    gen = Generator()
    rows = []
    for name, q, chunks in CASES:
        d = decide(q, chunks, site_id="S1", settings=SETTINGS, policy_router=ROUTER, gap=gap, generator=gen)
        rows.append({"case": name, "status": d.status, "reason": d.reason,
                     "calls_total": gen.calls, "gap_calls_total": gap.calls})
    matrix = {r["case"]: "%s/%s" % (r["status"], r["reason"]) for r in rows}
    metrics = {
        "cases": len(CASES),
        "refused": sum(1 for r in rows if r["status"].startswith("refuse")),
        "answered": sum(1 for r in rows if r["status"] == "answer"),
        "generator_calls": gen.calls,
        "gap_calls": gap.calls,
        "outcome_matrix": matrix,
        "rules_loaded": len(RULES),
    }
    print(json.dumps(metrics, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
