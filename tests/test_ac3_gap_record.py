# -*- coding: utf-8 -*-
"""AC3：每次拒答调用且仅调用一次知识缺口记录，且 reason 与触发分支一致；放行路径不调用。"""
from app.settings import Settings


def test_13_low_score_records_once(chunk, gen, ask, gap):
    ask("会议室怎么预定", [chunk("C1", score=0.05)], gen)
    assert gap.calls == 1
    assert gap.last()["reason"] == "low_score"
    assert gap.last()["site_id"] == "S1"


def test_14_insufficient_records_once(chunk, gen, ask, gap):
    s = Settings(min_rerank_score=0.35, min_evidence=2)
    ask("会议室怎么预定", [chunk("C1", score=0.9)], gen, settings=s)
    assert gap.calls == 1 and gap.last()["reason"] == "insufficient"


def test_15_stale_records_once(chunk, gen, ask, gap):
    ask("会议室怎么预定", [chunk("C1", valid_until="2018-01-01")], gen)
    assert gap.calls == 1 and gap.last()["reason"] == "stale_docs"


def test_16_policy_records_once(chunk, gen, ask, gap):
    ask("别家客户的报价是多少", [chunk("C1")], gen)
    assert gap.calls == 1 and gap.last()["reason"] == "policy"
    assert gap.last()["category"] == "business"


def test_17_citation_failed_records_once(chunk, gen, ask, gap):
    g = type(gen)(fake_chunk_id="C-X")
    ask("会议室怎么预定", [chunk("C1")], g)
    assert gap.calls == 1 and gap.last()["reason"] == "citation_failed"


def test_18_answer_path_no_gap_record(chunk, gen, ask, gap):
    d = ask("会议室怎么预定", [chunk("C1")], gen)
    assert d.status == "answer"
    assert gap.calls == 0
    assert gap.records == []


def test_19_gap_payload_has_question_and_time(chunk, gen, ask, gap):
    q = "独立办公室怎么收费"
    ask(q, [chunk("C1", score=0.02)], gen)
    body = gap.last()
    assert body["question"] == q
    assert body["asked_at"].endswith("Z")
