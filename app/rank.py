# -*- coding: utf-8 -*-
"""排序与月度对齐：排序只依赖程序计算的权重（簇大小 × 严重度），与模型输出无关。"""
import json

from app.embed import cosine
from app.summarize import centroid

SEVERITY_WEIGHT = {"critical": 3.0, "high": 2.0, "medium": 1.0, "low": 0.5}
DEFAULT_SEVERITY = "low"
ALIGN_THRESHOLD = 0.85


def severity_of(cases):
    weights = [SEVERITY_WEIGHT.get(c.get("severity") or DEFAULT_SEVERITY, SEVERITY_WEIGHT[DEFAULT_SEVERITY])
               for c in cases]
    return max(weights) if weights else SEVERITY_WEIGHT[DEFAULT_SEVERITY]


def score(size, severity_weight):
    return round(size * severity_weight, 4)


def rank_clusters(items, top_n=5):
    """items: [{cluster_id, size, severity_weight, min_case_key}]。排序键固定为程序量。"""
    ordered = sorted(items, key=lambda x: (-x["score"], -x["size"], x["min_case_key"]))
    return ordered[:top_n]


def align_with_previous(centers, prev_path=None, prev_centers=None):
    """centers: {cluster_id: (vector, name)}。返回 {cluster_id: (status, matched_prev_name, similarity)}。"""
    if prev_centers is None:
        prev_centers = []
        if prev_path:
            try:
                with open(prev_path, encoding="utf-8") as f:
                    prev_centers = json.load(f).get("centers", [])
            except FileNotFoundError:
                prev_centers = []
    matched_prev = set()
    status = {}
    for cid, (vec, name) in centers.items():
        best, best_name = 0.0, None
        for p in prev_centers:
            sim = cosine(vec, p["vector"])
            if sim > best:
                best, best_name = sim, p["name"]
        if best >= ALIGN_THRESHOLD:
            status[cid] = ("ongoing", best_name, round(best, 4))
            matched_prev.add(best_name)
        else:
            status[cid] = ("new", None, round(best, 4))
    vanished = [p["name"] for p in prev_centers if p["name"] not in matched_prev]
    return status, vanished


def save_centers(path, centers):
    payload = {"centers": [{"name": name, "vector": vec} for vec, name in centers.values()]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    return payload
