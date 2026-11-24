# -*- coding: utf-8 -*-
"""实测指标：在 200 条（+8 噪声）虚构失败用例上跑完整归因流水线，输出可复现数字。

数字全部来自本次运行：ARI、簇数与簇大小、噪声占比、切点距离、Top5 得分。
同时把归因样例写入 outputs/attribution_sample.json（草稿，review_status=pending）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.pipeline import load_cases, run

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")


def main():
    cases = load_cases()
    result = run(cases)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "attribution_sample.json"), "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in result.items() if k != "clusters"}, f, ensure_ascii=False, indent=2)

    metrics = dict(result["metrics"])
    metrics["top5"] = [(r["rank"], r["name"], r["size"], r["score"]) for r in result["top5"]]
    metrics["cluster_names"] = sorted(c["name"] for c in result["clusters"])
    metrics["alignment"] = result["alignment_summary"]
    print(json.dumps(metrics, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
