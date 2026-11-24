# -*- coding: utf-8 -*-
"""AC2：生成的模式名称超过 40 字时被截断或重试（mock 测试）。"""
from app.summarize import DESC_LIMIT, NAME_LIMIT, summarize_cluster

LONG = "这是一个明显超过四十个字上限的失败模式名称用于验证截断与重试逻辑是否真的生效并且不会外溢到报告里"


def _llm_factory(seq):
    calls = []

    def _llm(excerpts, hint=None):
        calls.append(hint)
        item = seq[min(len(calls) - 1, len(seq) - 1)]
        return {"name": item[0], "description": item[1]}

    _llm.calls = calls
    return _llm


def test_07_name_truncated_to_limit():
    llm = _llm_factory([(LONG, "说明")])
    out = summarize_cluster(["得分 0.34"], llm)
    assert len(out["name"]) <= NAME_LIMIT
    assert out["name"] == LONG[:NAME_LIMIT]
    assert out["truncated"] is True


def test_08_retry_with_hint_accepted():
    llm = _llm_factory([(LONG, "说明" * 80), ("短名称", "短说明")])
    out = summarize_cluster(["得分 0.34"], llm)
    assert out["name"] == "短名称"
    assert len(out["description"]) <= DESC_LIMIT
    assert out["truncated"] is False
    assert llm.calls[0] is None and llm.calls[1] and "不超过" in llm.calls[1]


def test_09_retry_still_long_falls_back_to_clip():
    llm = _llm_factory([(LONG, "说明"), (LONG, "说明")])
    out = summarize_cluster(["得分 0.34"], llm)
    assert len(out["name"]) <= NAME_LIMIT
    assert out["truncated"] is True
    assert out["attempts"][-1]["accepted"] is False
    assert len(out["attempts"]) == 2


def test_10_description_limit_enforced():
    llm = _llm_factory([("正常名称", "说明" * 200)])
    out = summarize_cluster(["引用悬空"], llm)
    assert len(out["description"]) <= DESC_LIMIT


def test_11_short_output_untouched():
    llm = _llm_factory([("阈值边界未命中", "得分低于阈值。")])
    out = summarize_cluster(["得分 0.34"], llm)
    assert out["name"] == "阈值边界未命中"
    assert out["truncated"] is False
    assert len(llm.calls) == 1


def test_12_baseline_names_within_limit(baseline):
    for cl in baseline["clusters"]:
        assert len(cl["name"]) <= NAME_LIMIT
        assert len(cl["description"]) <= DESC_LIMIT
