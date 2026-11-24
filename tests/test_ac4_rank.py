# -*- coding: utf-8 -*-
"""AC4：排序结果只依赖程序计算的权重，与模型输出无关。"""
from app.pipeline import run
from app.rank import rank_clusters, score, severity_of


def _rand_llm(seed=7):
    def _llm(excerpts, hint=None):
        return {"name": "名称%02d" % (seed + len(excerpts)), "description": "说明%02d" % seed}
    return _llm


def test_18_ranking_unchanged_when_names_replaced(mini_cases, mini_baseline):
    other = run(mini_cases, llm=_rand_llm())
    a = [(x["cluster_id"], x["size"], x["score"]) for x in mini_baseline["top5"]]
    b = [(x["cluster_id"], x["size"], x["score"]) for x in other["top5"]]
    assert a == b
    assert [x["name"] for x in other["top5"]] != [x["name"] for x in mini_baseline["top5"]]


def test_19_score_is_size_times_severity_weight():
    assert score(50, 3.0) == 150.0
    assert score(50, 2.0) == 100.0
    assert score(7, 0.5) == 3.5


def test_20_severity_uses_highest_in_cluster():
    cases = [{"severity": "low"}, {"severity": "critical"}, {"severity": "medium"}]
    assert severity_of(cases) == 3.0
    assert severity_of([{"severity": "unknown"}]) == 0.5


def test_21_tie_broken_by_size_then_case_key():
    items = [
        {"cluster_id": 3, "size": 10, "severity_weight": 2.0, "score": 20.0, "min_case_key": "C-9"},
        {"cluster_id": 1, "size": 20, "severity_weight": 1.0, "score": 20.0, "min_case_key": "C-1"},
        {"cluster_id": 2, "size": 5, "severity_weight": 3.0, "score": 15.0, "min_case_key": "C-2"},
    ]
    order = [x["cluster_id"] for x in rank_clusters(items, top_n=3)]
    assert order == [1, 3, 2]


def test_22_top_n_limits_length(mini_baseline):
    assert len(mini_baseline["top5"]) <= 5
    items = [{"cluster_id": i, "size": 10 - i, "severity_weight": 1.0, "score": 10 - i,
              "min_case_key": "C-%d" % i} for i in range(8)]
    assert len(rank_clusters(items, top_n=5)) == 5
