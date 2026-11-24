# -*- coding: utf-8 -*-
"""归因流水线：失败描述 → 向量化 → 聚类 → 代表用例 → LLM 摘要 → 程序排序 → 月度对齐。"""
import json
import os

from app.cluster import adjusted_rand_index, hdbscan_lite
from app.embed import embed
from app.rank import align_with_previous, rank_clusters, score, severity_of
from app.summarize import centroid, pick_representatives, stub_llm, summarize_cluster

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(HERE, "fixtures", "failures_200.json")


def describe(case):
    return "[%s] %s | 未命中：%s | 违规：%s | 输出摘要：%s" % (
        case.get("tool") or "-",
        ",".join(case.get("tags") or []) or "-",
        "；".join(case.get("missed_points") or []) or "无",
        ",".join(case.get("violation_types") or []) or "无",
        (case.get("output_excerpt") or "")[:300])


def load_cases(path=FIXTURES):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run(cases, llm=stub_llm, min_cluster_size=5, prev_path=None, top_n=5, compute_ari=True):
    texts = [describe(c) for c in cases]
    vecs = embed(texts)
    labels, info = hdbscan_lite(vecs, min_cluster_size=min_cluster_size)

    clusters = []
    for cid in sorted(set(labels) - {-1}):
        idxs = [i for i, l in enumerate(labels) if l == cid]
        member_vecs = [vecs[i] for i in idxs]
        reps = pick_representatives(member_vecs, k=min(3, len(idxs)))
        rep_cases = [cases[idxs[r]] for r in reps]
        summary = summarize_cluster([describe(c) for c in rep_cases], llm)
        sev_w = severity_of([cases[i] for i in idxs])
        clusters.append({
            "cluster_id": cid,
            "size": len(idxs),
            "severity_weight": sev_w,
            "score": score(len(idxs), sev_w),
            "min_case_key": min(cases[i]["case_key"] for i in idxs),
            "name": summary["name"],
            "description": summary["description"],
            "truncated": summary["truncated"],
            "attempts": summary["attempts"],
            "representatives": [c["case_key"] for c in rep_cases],
            "case_keys": [cases[i]["case_key"] for i in idxs],
            "centroid": centroid(member_vecs),
        })

    ranked = rank_clusters(clusters, top_n=top_n)

    centers = {c["cluster_id"]: (c["centroid"], c["name"]) for c in clusters}
    status, vanished = align_with_previous(centers, prev_path=prev_path)
    for c in clusters:
        st, prev_name, sim = status.get(c["cluster_id"], ("new", None, 0.0))
        c["alignment"] = {"status": st, "matched": prev_name, "similarity": sim}

    noise_keys = [cases[i]["case_key"] for i, l in enumerate(labels) if l == -1]
    metrics = {
        "cases": len(cases),
        "clusters": info["clusters"],
        "noise_cases": len(noise_keys),
        "noise_ratio": round(len(noise_keys) / len(cases), 4) if cases else 0.0,
        "cut_weight": info.get("cut_weight"),
    }
    if compute_ari:
        truth = [c.get("pattern") or "noise" for c in cases]
        metrics["ari_all"] = round(adjusted_rand_index(truth, labels), 4)
        keep = [i for i, l in enumerate(labels) if l != -1]
        if keep:
            metrics["ari_non_noise"] = round(
                adjusted_rand_index([truth[i] for i in keep], [labels[i] for i in keep]), 4)

    return {
        "clusters": clusters,
        "top5": [{"rank": i + 1, "cluster_id": c["cluster_id"], "name": c["name"],
                  "size": c["size"], "score": c["score"],
                  "representatives": c["representatives"]} for i, c in enumerate(ranked)],
        "alignment_summary": {
            "new": [c["name"] for c in clusters if c["alignment"]["status"] == "new"],
            "ongoing": [c["name"] for c in clusters if c["alignment"]["status"] == "ongoing"],
            "vanished": vanished,
        },
        "noise_cases": noise_keys,
        "metrics": metrics,
        "review_status": "pending",
        "review_level": "人工复核（月报审阅人确认或改写后方可发布）",
    }


if __name__ == "__main__":
    out = run(load_cases())
    print(json.dumps(out["metrics"], ensure_ascii=False))
    for row in out["top5"]:
        print(row["rank"], row["cluster_id"], row["name"], row["size"], row["score"], row["representatives"])
