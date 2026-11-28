"""JSON Schema 机械校验测试（返工整改：输出必须符合 app/schema.json）。

覆盖：
- 合规输出通过；
- 缺 not_found / 额外键 / quote 超长超短 / confidence_self 越界 / 类型错误 被拒；
- 单对象候选规范化后合规；
- extract_group 对不合规输出与非法 JSON 同一口径：重试、3 次仍失败标 llm_failed。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.extractor import extract_group
from app.mock_llm import MockLLM
from app.schema_check import is_valid, load_schema, validate
from app.store import CallLogStore

STRUCTURE = {
    "term": {"effective_date": "生效日", "expiry_date": "到期日", "term_desc": "期限描述"},
}


def _item(**over):
    base = {"value": "2026-01-01", "quote": "本合同自 2026 年 1 月 1 日起生效",
            "confidence_self": 0.9, "not_found": False}
    base.update(over)
    return {k: v for k, v in base.items() if v is not ...}


def test_schema_file_loads_and_has_not_found():
    """schema.json 必须声明 not_found（订单点名的第四个键）。"""
    schema = load_schema()
    item_schema = schema["properties"]["fields"]["additionalProperties"]["items"]
    assert "not_found" in item_schema["required"]
    assert "not_found" in item_schema["properties"]


def test_valid_output_passes():
    assert is_valid({"fields": {"effective_date": [_item()]}}) is True


def test_single_object_candidate_normalized_passes():
    """单对象候选（非数组）原始结构不合规，但 extract_group 规范化后合规。"""
    from app.extractor import _normalize_for_schema
    parsed = {"fields": {"effective_date": _item()}}
    assert is_valid(parsed) is False                       # 原始：应为数组
    assert is_valid(_normalize_for_schema(parsed)) is True  # 规范化后合规


def test_missing_not_found_rejected():
    bad = _item(not_found=...)   # 移除该键
    errs = validate({"fields": {"effective_date": [bad]}})
    assert any("not_found" in e for e in errs)
    assert is_valid({"fields": {"effective_date": [bad]}}) is False


def test_extra_key_rejected():
    errs = validate({"fields": {"effective_date": [_item(extra="x")]}})
    assert any("额外键" in e for e in errs)


def test_quote_length_bounds_rejected():
    assert not is_valid({"fields": {"effective_date": [_item(quote="abc")]}})       # <4
    assert not is_valid({"fields": {"effective_date": [_item(quote="字" * 201)]}})  # >200


def test_confidence_bounds_and_type_rejected():
    assert not is_valid({"fields": {"effective_date": [_item(confidence_self=1.5)]}})
    assert not is_valid({"fields": {"effective_date": [_item(confidence_self="高")]}})
    assert not is_valid({"fields": {"effective_date": [_item(value=123)]}})
    assert not is_valid({"fields": {"effective_date": [_item(not_found="no")]}})


def test_missing_fields_key_rejected():
    assert not is_valid({"result": {}})


def test_extract_group_retries_schema_invalid_then_llm_failed():
    """3 次返回缺 not_found 的输出 -> 与非法 JSON 同口径，整组 llm_failed。"""
    store = CallLogStore()
    bad = json.dumps({"fields": {"effective_date": [_item(not_found=...)]}},
                     ensure_ascii=False)
    llm = MockLLM([bad])
    res = extract_group("任意原文", STRUCTURE, "term", llm, store)
    assert res.llm_failed is True
    assert len(llm.calls) == 3            # 1 + 2 次重试
    assert len(store.calls_for_group("term")) == 3


def test_extract_group_second_attempt_valid_succeeds():
    """第 1 次缺 not_found、第 2 次合规 -> 不标 llm_failed，正常抽取。"""
    store = CallLogStore()
    bad = json.dumps({"fields": {"effective_date": [_item(not_found=...)]}},
                     ensure_ascii=False)
    good = json.dumps({"fields": {"effective_date": [_item()]}}, ensure_ascii=False)
    llm = MockLLM([bad, good])
    res = extract_group("本合同自 2026 年 1 月 1 日起生效，至 2026 年 12 月 31 日到期。"*5,
                        STRUCTURE, "term", llm, store)
    assert res.llm_failed is False
    assert res.fields["effective_date"].value == "2026-01-01"
    assert len(llm.calls) == 2
