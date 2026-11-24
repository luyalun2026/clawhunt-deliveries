# -*- coding: utf-8 -*-
"""边界与加固：噪声参与度、退化数据、向量器契约、描述截断、ARI 边界。"""
from app.cluster import adjusted_rand_index, hdbscan_lite
from app.embed import DIM, embed
from app.pipeline import describe, run


def test_23_noise_not_in_top5(baseline):
    noise = set(baseline["noise_cases"])
    for row in baseline["top5"]:
        assert not (set(row["representatives"]) & noise)


def test_24_single_cluster_of_exactly_five():
    rows = [{"case_key": "S-%02d" % i, "pattern": "P", "tool": "t", "tags": ["a"],
             "missed_points": ["p"], "violation_types": ["v"], "severity": "medium",
             "output_excerpt": "完全相同的模式文本 第 %d 条" % i} for i in range(5)]
    out = run(rows, compute_ari=False)
    assert out["metrics"]["clusters"] == 1
    assert out["clusters"][0]["size"] == 5


def test_25_all_identical_points_collapse_to_one():
    vecs = embed(["同一句话"] * 8)
    labels, info = hdbscan_lite(vecs, 5)
    assert info["degenerate"] is True
    assert info["clusters"] == 1 and info["cluster_sizes"] == [8]
    assert all(l == 0 for l in labels)


def test_26_empty_input():
    out = run([], compute_ari=False)
    assert out["metrics"]["cases"] == 0
    assert out["clusters"] == []


def test_27_describe_truncates_excerpt_to_300():
    case = {"tool": "t", "tags": ["a"], "missed_points": ["p"], "violation_types": ["v"],
            "output_excerpt": "长" * 500}
    text = describe(case)
    assert text.count("长") == 300


def test_28_embed_dimension_and_norm():
    vecs = embed(["引用悬空：引用片段 c-1042 不在给定切片集合中", "工具参数类型错误"])
    assert len(vecs) == 2 and len(vecs[0]) == DIM
    norm = sum(v * v for v in vecs[0]) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_29_ari_identity_is_one():
    assert adjusted_rand_index([1, 2, 3, 4], [1, 2, 3, 4]) == 1.0


def test_30_ari_all_one_cluster():
    assert adjusted_rand_index([1, 2, 3], [0, 0, 0]) == 0.0


def test_31_review_status_pending(baseline):
    assert baseline["review_status"] == "pending"
    assert "人工复核" in baseline["review_level"]
