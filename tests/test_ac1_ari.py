# -*- coding: utf-8 -*-
"""AC1：4 种人为构造失败模式 × 50 + 8 噪声，聚类 ARI ≥ 0.7（实测值写入报告）。"""
from app.cluster import adjusted_rand_index
from app.embed import embed
from app.cluster import hdbscan_lite
from app.pipeline import describe


def test_01_ari_above_threshold(baseline):
    m = baseline["metrics"]
    assert m["ari_all"] >= 0.7, m
    assert m["ari_non_noise"] >= 0.7, m
    print("ARI all=%.4f non_noise=%.4f" % (m["ari_all"], m["ari_non_noise"]))


def test_02_four_clusters_recovered(baseline):
    sizes = sorted(c["size"] for c in baseline["clusters"])
    assert len(baseline["clusters"]) == 4, sizes
    assert sizes == [50, 50, 50, 50]


def test_03_noise_isolated(baseline):
    m = baseline["metrics"]
    assert m["noise_cases"] == 8
    assert m["noise_ratio"] < 0.05
    assert all(k.startswith("N-") for k in baseline["noise_cases"])


def test_04_cluster_purity(cases, baseline):
    truth = {c["case_key"]: (c.get("pattern") or "noise") for c in cases}
    for cl in baseline["clusters"]:
        labels = {truth[k] for k in cl["case_keys"]}
        assert len(labels) == 1, (cl["cluster_id"], labels)


def test_05_ari_matches_direct_call(cases, baseline):
    texts = [describe(c) for c in cases]
    vecs = embed(texts)
    labels, info = hdbscan_lite(vecs, min_cluster_size=5)
    truth = [c.get("pattern") or "noise" for c in cases]
    assert round(adjusted_rand_index(truth, labels), 4) == baseline["metrics"]["ari_all"]
    assert info["clusters"] == 4


def test_06_cut_weight_is_recorded(baseline):
    assert baseline["metrics"]["cut_weight"] is not None
    assert baseline["metrics"]["cut_weight"] > 0
