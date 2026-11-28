# -*- coding: utf-8 -*-
"""边界与加固：可见范围、引用校验归一化、配置校验、政策优先级。"""
import os
import tempfile

import pytest

from app.policy import RuleConfigError, load_rules
from app.refusal import REFUSAL_TEXT, verify_citations
from app.settings import Settings


class CiteGen:
    def __init__(self, citations):
        self.citations = citations
        self.calls = 0

    def __call__(self, *, question, chunks):
        self.calls += 1
        return {"answer": "ok", "citations": self.citations}


def test_24_cross_site_not_counted(chunk, gen, ask):
    s = Settings(min_rerank_score=0.35, min_evidence=2)
    d = ask("会议室怎么预定", [chunk("C1", score=0.9, site="S1"), chunk("C2", score=0.9, site="S2")],
            gen, settings=s)
    assert d.reason == "insufficient"
    assert gen.calls == 0


def test_25_classification_above_user_filtered(chunk, gen, ask):
    s = Settings(min_rerank_score=0.35, min_evidence=2)
    d = ask("会议室怎么预定",
            [chunk("C1", score=0.9, classification=1), chunk("C2", score=0.9, classification=3)],
            gen, settings=s, user_level=2)
    assert d.reason == "insufficient"


def test_26_soft_deleted_excluded(chunk, gen, ask):
    d = ask("会议室怎么预定", [chunk("C1", score=0.9, deleted="2026-11-01T00:00:00Z")], gen)
    assert d.status == "refuse_kb" and d.reason == "insufficient"


def test_27_citation_nfkc_equivalent_passes(chunk, gen, ask):
    c = chunk("C1", text="会议室按１２０分钟起订，超时按半小时计。")
    g = CiteGen([{"chunk_id": "C1", "snippet": "120分钟起订"}])
    d = ask("会议室怎么预定", [c], g)
    assert d.status == "answer", d


def test_28_citation_snippet_mismatch_refuses(chunk, gen, ask):
    class Rewritten:
        calls = 0

        def __call__(self, *, question, chunks):
            self.calls += 1
            return {"answer": "ok", "citations": [{"chunk_id": "C1", "snippet": "完全改写的片段文字"}]}

    g = Rewritten()
    d = ask("会议室怎么预定", [chunk("C1")], g)
    assert d.status == "refuse_kb" and d.reason == "citation_failed"
    assert d.answer == REFUSAL_TEXT


def test_29_settings_defaults_from_env(monkeypatch):
    for k in ("KB_MIN_RERANK_SCORE", "KB_MIN_EVIDENCE", "DOC_FRESHNESS_DAYS", "KB_GAP_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    s = Settings.from_env()
    assert (s.min_rerank_score, s.min_evidence, s.doc_freshness_days) == (0.35, 1, 180)
    assert set(s.used_defaults) == {"KB_MIN_RERANK_SCORE", "KB_MIN_EVIDENCE",
                                    "DOC_FRESHNESS_DAYS", "KB_GAP_BASE_URL"}


def test_30_settings_from_env_overrides(monkeypatch):
    monkeypatch.setenv("KB_MIN_RERANK_SCORE", "0.5")
    monkeypatch.setenv("KB_MIN_EVIDENCE", "2")
    s = Settings.from_env()
    assert s.min_rerank_score == 0.5 and s.min_evidence == 2
    assert "KB_MIN_RERANK_SCORE" not in s.used_defaults


def _write(tmp_path, text):
    p = tmp_path / "rules.yaml"
    p.write_text(text, encoding="utf-8")
    return str(p)


BASE = """
rules:
  - id: {id1}
    category: {cat1}
    pattern: "x"
    keywords: ["x"]
    examples: {ex1}
  - id: {id2}
    category: business
    pattern: "y"
    keywords: ["y"]
    examples: ["a", "b", "c"]
  - id: COMMIT-X
    category: commitment
    pattern: "z"
    keywords: ["z"]
    examples: ["a", "b", "c"]
"""


def test_31_rule_with_too_few_examples_rejected(tmp_path):
    path = _write(tmp_path, BASE.format(id1="C-1", cat1="contact", ex1='["a", "b"]',
                                        id2="B-1"))
    with pytest.raises(RuleConfigError) as e:
        load_rules(path)
    assert "样例不足" in str(e.value)


def test_32_duplicate_rule_id_rejected(tmp_path):
    path = _write(tmp_path, BASE.format(id1="B-1", cat1="contact", ex1='["a", "b", "c"]',
                                        id2="B-1"))
    with pytest.raises(RuleConfigError) as e:
        load_rules(path)
    assert "重复" in str(e.value)


def test_33_policy_beats_low_score(chunk, gen, ask, gap):
    d = ask("其他会员的手机号能给我吗", [chunk("C1", score=0.01)], gen)
    assert d.status == "refuse_policy"
    assert gap.last()["reason"] == "policy"


def test_34_verify_citations_reports_missing_chunk(chunk):
    ok, bad = verify_citations("x", [{"chunk_id": "NOPE", "snippet": "y"}], [chunk("C1")])
    assert ok is False and bad[0]["why"] == "chunk_not_found"


def test_35_decide_marks_review_level_l0(chunk, gen, ask):
    d = ask("会议室怎么预定", [chunk("C1")], gen)
    assert d.review_level == "L0"
