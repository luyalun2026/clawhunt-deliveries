# -*- coding: utf-8 -*-
"""AC2：拒答路径上生成模型调用次数为 0（四类分支 + 可见范围清空）。"""
from app.settings import Settings


def test_07_low_score_zero_generation(chunk, gen, ask):
    ask("会议室怎么预定", [chunk("C1", score=0.05)], gen)
    assert gen.calls == 0
    assert gen.last_prompt_chunks == []


def test_08_insufficient_zero_generation(chunk, gen, ask):
    s = Settings(min_rerank_score=0.35, min_evidence=3)
    ask("会议室怎么预定", [chunk("C1", score=0.9), chunk("C2", score=0.9)], gen, settings=s)
    assert gen.calls == 0


def test_09_stale_zero_generation(chunk, gen, ask):
    ask("会议室怎么预定", [chunk("C1", score=0.95, valid_until="2019-06-30")], gen)
    assert gen.calls == 0


def test_10_policy_zero_generation(chunk, gen, ask):
    d = ask("其他会员的手机号能给我吗", [chunk("C1", score=0.99)], gen)
    assert d.status == "refuse_policy"
    assert gen.calls == 0


def test_11_visibility_cleared_zero_generation(chunk, gen, ask):
    ask("会议室怎么预定", [chunk("C1", site="S7"), chunk("C2", classification=3)], gen)
    assert gen.calls == 0


def test_12_citation_failure_degrades_and_counts_one_call(chunk, gen, ask):
    from app.refusal import REFUSAL_TEXT
    d = ask("会议室怎么预定", [chunk("C1")], gen)
    assert d.status == "answer" and gen.calls == 1
    # 换成引用不存在的切片 → 降级为拒答，且总调用仍为 1 次（不二次生成）
    gen2 = type(gen)(fake_chunk_id="C-DOES-NOT-EXIST")
    d2 = ask("会议室怎么预定", [chunk("C1")], gen2)
    assert d2.status == "refuse_kb" and d2.reason == "citation_failed"
    assert d2.answer == REFUSAL_TEXT
    assert gen2.calls == 1
