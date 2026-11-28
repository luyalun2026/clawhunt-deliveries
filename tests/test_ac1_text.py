# -*- coding: utf-8 -*-
"""AC1：低于阈值 / 切片不足 / 全过期 的文案必须与固定文案逐字一致；阈值边界等于阈值时不拒答。"""
from app.refusal import REFUSAL_TEXT
from app.settings import Settings

FIXED = "知识库中没有找到；已记录为知识缺口，负责人会补充。"


def test_01_low_score_text_exact(chunk, gen, ask, gap):
    d = ask("会议室怎么预定", [chunk("C1", score=0.10)], gen)
    assert d.status == "refuse_kb" and d.reason == "low_score"
    assert d.answer == FIXED
    assert d.answer == REFUSAL_TEXT
    assert len(d.answer) == len(FIXED)


def test_02_insufficient_text_exact(chunk, gen, ask):
    s = Settings(min_rerank_score=0.35, min_evidence=2)
    d = ask("会议室怎么预定", [chunk("C1", score=0.9), chunk("C2", score=0.1)], gen, settings=s)
    assert d.reason == "insufficient"
    assert d.answer == FIXED


def test_03_stale_docs_text_exact(chunk, gen, ask):
    d = ask("会议室怎么预定", [chunk("C1", score=0.9, valid_until="2020-01-01")], gen)
    assert d.reason == "stale_docs"
    assert d.answer == FIXED


def test_04_score_equal_threshold_passes(chunk, gen, ask):
    d = ask("会议室怎么预定", [chunk("C1", score=0.35)], gen)
    assert d.status == "answer", d
    assert gen.calls == 1


def test_05_just_below_threshold_refuses(chunk, gen, ask):
    d = ask("会议室怎么预定", [chunk("C1", score=0.3499)], gen)
    assert d.status == "refuse_kb" and d.reason == "low_score"


def test_06_empty_after_visibility_filter(chunk, gen, ask):
    d = ask("会议室怎么预定", [chunk("C1", site="S9")], gen)
    assert d.status == "refuse_kb" and d.reason == "insufficient"
    assert d.answer == FIXED
