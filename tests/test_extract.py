"""S5-DOC-010 llm_extract 测试套件（对应验收标准 4 条 + 边界补充）。"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.extractor import (
    chunk_text, extract_group, extract_all, normalize,
    parse_amounts, quote_backcheck, build_review_queue,
)
from app.mock_llm import MockLLM
from app.prompts import FIELD_GROUPS, PROMPT_VERSIONS
from app.store import CallLogStore

STRUCTURE = {
    "subject": {"party_a": "甲方名称", "party_b": "乙方名称", "contract_name": "合同名称"},
    "term": {"effective_date": "生效日", "expiry_date": "到期日", "term_desc": "期限描述"},
    "amount_payment": {"total_amount_quote": "总金额原文片段", "payment_terms_quote": "付款条款原文片段"},
    "rights": {"member_rights": "会员权益", "service_scope": "服务范围"},
    "clauses": {"termination_clause": "解除条款", "liability_clause": "违约责任", "dispute_clause": "争议解决"},
}

SAMPLE = (
    "会员服务合同（虚构样例）\n甲方：星辰科技（虚构）有限公司\n乙方：蓝湾商务服务（虚构）股份有限公司。"
    "合同名称：会员空间服务合同。本合同自 2026 年 1 月 1 日起生效，至 2026 年 12 月 31 日到期，服务期限一年。"
    "总金额为人民币 12 万元（¥120000 元），分四期支付，每季度末支付 3 万元。"
    "会员权益：共享办公工位、会议室预约、产业对接活动。服务范围：武汉市内两处场地。"
    "解除条款：任一方提前 30 日书面通知可解除。违约责任：违约方赔偿守约方直接损失。"
    "争议解决：提交武汉仲裁委员会仲裁。"
)


# ---------- AC1 ----------
def test_ac1_quote_not_in_source_marked():
    """AC1：mock 返回不存在于原文的 quote -> quote_not_found 且 value 为空。"""
    store = CallLogStore()
    llm = MockLLM([MockLLM.ok({
        "party_a": [{"value": "不存在公司", "quote": "这句话原文里根本没有出现哦", "confidence_self": 0.9}],
        "party_b": [{"value": "蓝湾商务服务（虚构）股份有限公司",
                     "quote": "乙方：蓝湾商务服务（虚构）股份有限公司", "confidence_self": 0.95}],
        "contract_name": [],
    })])
    res = extract_group(SAMPLE, STRUCTURE, "subject", llm, store)
    pa = res.fields["party_a"]
    assert pa.quote_not_found is True
    assert pa.value is None
    assert pa.not_found is True
    pb = res.fields["party_b"]
    assert pb.quote_not_found is False
    assert pb.value == "蓝湾商务服务（虚构）股份有限公司"


# ---------- AC2 ----------
def test_ac2_three_bad_json_marks_llm_failed():
    """AC2：mock 连续 3 次返回非法 JSON -> 整组 llm_failed。"""
    store = CallLogStore()
    llm = MockLLM([None])  # None 之后永远返回不可解析文本
    res = extract_group(SAMPLE, STRUCTURE, "term", llm, store)
    assert res.llm_failed is True
    for f in res.fields.values():
        assert f.llm_failed is True
    assert len(store.calls_for_group("term")) == 3  # 1 + 2 次重试


def test_ac2b_retry_then_success():
    """边界：前 2 次坏 JSON、第 3 次成功 -> 不应 llm_failed。"""
    store = CallLogStore()
    llm = MockLLM([None, None, MockLLM.ok({
        "effective_date": [{"value": "2026-01-01", "quote": "本合同自 2026 年 1 月 1 日起生效",
                            "confidence_self": 0.9}],
        "expiry_date": [], "term_desc": [],
    })])
    res = extract_group(SAMPLE, STRUCTURE, "term", llm, store)
    assert res.llm_failed is False
    assert res.fields["effective_date"].value == "2026-01-01"


# ---------- AC3 ----------
def test_ac3_chunk_overlap_exact_300():
    """AC3：20000 字虚构长合同切块，相邻块重叠恰 300 字。"""
    text = "".join(f"第{i}条：这是虚构条款内容，用于长度填充测试。" * 3 for i in range(400))[:20000]
    assert len(text) == 20000
    chunks = chunk_text(text)
    assert chunks[0]["end"] - chunks[0]["start"] == 6000
    for a, b in zip(chunks, chunks[1:]):
        overlap_text = text[b["start"]:a["end"]]
        assert len(overlap_text) == 300
        assert a["text"][6000 - 300:] == b["text"][:300]
    assert chunks[-1]["end"] == 20000


def test_ac3b_chunks_respect_max_size():
    text = "字" * 13000
    chunks = chunk_text(text)
    assert all(c["end"] - c["start"] <= 6000 for c in chunks)


# ---------- AC4 ----------
def test_ac4_call_log_records_version_and_model():
    """AC4：每次调用记录 prompt_version 与模型名，可在库中查到。"""
    store = CallLogStore()
    llm = MockLLM([MockLLM.ok({
        "total_amount_quote": [{"value": "¥120000 元", "quote": "总金额为人民币 12 万元（¥120000 元）",
                                "confidence_self": 0.93}],
        "payment_terms_quote": [{"value": "分四期支付", "quote": "分四期支付，每季度末支付 3 万元",
                                 "confidence_self": 0.88}],
    })])
    extract_group(SAMPLE, STRUCTURE, "amount_payment", llm, store, model="doc-llm-mock")
    rows = store.calls_for_group("amount_payment")
    assert len(rows) == 1
    assert rows[0]["prompt_version"] == PROMPT_VERSIONS["amount_payment"] == "1.0"
    assert rows[0]["model"] == "doc-llm-mock"
    assert rows[0]["parse_ok"] == 1


def test_ac4b_all_groups_logged():
    store = CallLogStore()
    llm = MockLLM([MockLLM.ok({})])
    extract_all(SAMPLE, STRUCTURE, llm, store)
    assert store.count() == len(FIELD_GROUPS) == 5
    for g in FIELD_GROUPS:
        assert store.calls_for_group(g)[0]["prompt_version"] == "1.0"


# ---------- 补充边界 ----------
def test_quote_length_bounds():
    assert quote_backcheck("ab", SAMPLE) is False              # <4 字
    assert quote_backcheck("字" * 201, "字" * 300) is False     # >200 字
    assert quote_backcheck("乙方：蓝湾商务服务", SAMPLE) is True


def test_quote_normalized_match_fullwidth():
    """全半角/空白差异走归一化匹配。"""
    src = "合同金额：１２万元整（含税）"
    assert quote_backcheck("合同金额：12万元整", src) is True   # 全角数字 NFKC 归一
    assert quote_backcheck("合同 金 额：12 万元整", src) is True  # 空白差异


def test_merge_picks_highest_confidence_backcheckable():
    """两块给出同字段候选：回查失败者淘汰，取回查成功中置信度最高者。"""
    store = CallLogStore()
    llm = MockLLM([MockLLM.ok({
        "member_rights": [
            {"value": "坏候选", "quote": "不存在的原文片段哈", "confidence_self": 0.99},
            {"value": "共享办公工位、会议室预约、产业对接活动", "quote": "会员权益：共享办公工位、会议室预约、产业对接活动",
             "confidence_self": 0.80},
        ],
        "service_scope": [],
    })])
    res = extract_group(SAMPLE, STRUCTURE, "rights", llm, store)
    mr = res.fields["member_rights"]
    assert mr.value == "共享办公工位、会议室预约、产业对接活动"
    assert mr.confidence_self == 0.80


def test_amounts_parsed_by_program_not_llm():
    out = parse_amounts(SAMPLE)
    assert "120000元" in out and "3万元" in out


def test_review_queue_all_rows_flagged():
    store = CallLogStore()
    llm = MockLLM([MockLLM.ok({})])
    results = extract_all(SAMPLE, STRUCTURE, llm, store)
    rows = build_review_queue(results)
    assert rows and all(r["needs_human_review"] for r in rows)
