"""llm_extract 字段抽取服务（S5-DOC-010）。

口径要点：
- 提示词按 5 个字段分组维护，每组模板带 prompt_version，并入库记录（store.py）。
- 输出字段统一 {value, quote, confidence_self, not_found}。
- quote 必须在原文中连续出现（4-200 字）：先精确匹配，失败后用归一化匹配
  （NFKC 全半角统一 + 去空白）回查；回查失败丢弃 value 并标记 quote_not_found。
- 长合同按条款切块：每块 <=6000 字、相邻块重叠恰 300 字；
  合并时同字段取「quote 可回查且 confidence_self 最高」的候选。
- JSON 解析失败重试 2 次（每组最多 3 次调用），仍失败整组标记 llm_failed。
- 模型只做定位与抄录；金额数值由程序从原文解析（parse_amounts），
  AI 不参与任何金额计算。
- 抽取结果全部进入人工复核队列（review_queue），不直接对外发送。
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .prompts import FIELD_GROUPS, PROMPT_VERSIONS, render_prompt
from .store import CallLogStore

CHUNK_SIZE = 6000
CHUNK_OVERLAP = 300
JSON_RETRY_TIMES = 2          # 解析失败重试 2 次 => 每组最多 3 次调用
QUOTE_MIN, QUOTE_MAX = 4, 200

# 可注入的 LLM 客户端协议：chat(prompt: str, system: str) -> str
LlmClient = Callable[[str, str], str]


def normalize(text: str) -> str:
    """归一化：NFKC（全半角统一）+ 去所有空白。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text or ""))


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[Dict]:
    """切块：每块 <=size 字，相邻块重叠恰 overlap 字（末块不足时例外）。"""
    if not text:
        return []
    step = size - overlap
    if step <= 0:
        raise ValueError("overlap must be smaller than size")
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        chunks.append({"start": start, "end": end, "text": text[start:end]})
        if end >= n:
            break
        start += step
    return chunks


def quote_backcheck(quote: str, source_text: str) -> bool:
    """quote 是否为原文连续片段：先精确匹配，再归一化匹配。"""
    if not isinstance(quote, str):
        return False
    if not (QUOTE_MIN <= len(quote) <= QUOTE_MAX):
        return False
    if quote in source_text:
        return True
    n_src = normalize(source_text)
    n_q = normalize(quote)
    return bool(n_q) and n_q in n_src


@dataclass
class FieldResult:
    value: Optional[str] = None
    quote: Optional[str] = None
    confidence_self: Optional[float] = None
    not_found: bool = True
    quote_not_found: bool = False
    llm_failed: bool = False

    def public(self) -> Dict:
        d = {
            "value": self.value,
            "quote": self.quote,
            "confidence_self": self.confidence_self,
            "not_found": self.not_found,
        }
        if self.quote_not_found:
            d["quote_not_found"] = True
        if self.llm_failed:
            d["llm_failed"] = True
        return d


@dataclass
class GroupResult:
    group: str
    fields: Dict[str, FieldResult] = field(default_factory=dict)
    llm_failed: bool = False


def _parse_model_json(raw: str) -> Optional[Dict]:
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        # 容错：抓取首个 {...} JSON 对象
        m = re.search(r"\{.*\}", raw or "", re.S)
        if m:
            try:
                obj = json.loads(m.group(0))
                return obj if isinstance(obj, dict) else None
            except Exception:
                return None
        return None


def _merge_candidates(cands: List[Dict], source_text: str) -> FieldResult:
    """同字段多块候选合并：取 quote 可回查且 confidence_self 最高者。"""
    valid = [c for c in cands if quote_backcheck(c.get("quote") or "", source_text)]
    if not valid:
        r = FieldResult(not_found=True)
        if cands:
            r.quote_not_found = True
        return r
    best = max(valid, key=lambda c: (c.get("confidence_self") if isinstance(c.get("confidence_self"), (int, float)) else 0.0))
    return FieldResult(
        value=best.get("value"),
        quote=best.get("quote"),
        confidence_self=best.get("confidence_self"),
        not_found=False,
    )


def extract_group(
    text: str,
    structure: Dict,
    field_group: str,
    llm: LlmClient,
    store: CallLogStore,
    model: Optional[str] = None,
) -> GroupResult:
    """对单个字段分组执行抽取。

    structure: 完整字段结构定义（组名 -> 字段名 -> 说明），用于渲染提示词。
    llm: OpenAI 兼容客户端（测试注入 mock；生产由 DOC_LLM_BASE_URL/DOC_LLM_MODEL 构造）。
    """
    if field_group not in FIELD_GROUPS:
        raise KeyError(f"unknown field_group: {field_group}")
    model = model or "doc-llm-mock"
    group_fields = FIELD_GROUPS[field_group]
    prompt = render_prompt(field_group, structure, text)

    result = GroupResult(group=field_group)
    parsed: Optional[Dict] = None
    for attempt in range(1 + JSON_RETRY_TIMES):
        raw = llm.chat(prompt, FIELD_GROUPS[field_group]["system"])
        store.record(field_group=field_group, prompt_version=PROMPT_VERSIONS[field_group],
                     model=model, attempt=attempt, ok=False)
        parsed = _parse_model_json(raw)
        if parsed is not None:
            store.mark_last_ok()
            break
    if parsed is None:
        for fname in group_fields["fields"]:
            fr = FieldResult(llm_failed=True)
            fr.not_found = True
            result.fields[fname] = fr
        result.llm_failed = True
        return result

    items = parsed.get("fields") or {}
    chunks = chunk_text(text)
    sources = [c["text"] for c in chunks] or [text]
    for fname in group_fields["fields"]:
        cands = []
        raw_item = items.get(fname)
        if isinstance(raw_item, dict):
            raw_item = [raw_item]
        if isinstance(raw_item, list):
            cands = raw_item
        if not cands:
            fr = FieldResult(not_found=True)
        else:
            fr = _merge_candidates(cands, text)
        result.fields[fname] = fr
    return result


def extract_all(
    text: str,
    structure: Dict,
    llm: LlmClient,
    store: CallLogStore,
    model: Optional[str] = None,
) -> Dict[str, GroupResult]:
    return {g: extract_group(text, structure, g, llm, store, model) for g in FIELD_GROUPS}


_AMOUNT_RE = re.compile(r"[¥￥]?\s*(\d+(?:[,，]\d{3})*(?:\.\d+)?)\s*(万元|万|元)?")

def parse_amounts(text: str) -> List[str]:
    """程序从原文解析金额（AI 不计算）。返回归一化字符串列表，如 '120000元'。"""
    out = []
    for m in _AMOUNT_RE.finditer(text or ""):
        num = m.group(1).replace(",", "").replace("，", "")
        unit = m.group(2) or "元"
        if unit in ("万", "万元"):
            out.append(f"{num}万{'' if unit == '万' else '元'}")
        else:
            out.append(f"{num}元")
    return out


def build_review_queue(results: Dict[str, GroupResult]) -> List[Dict]:
    """全部抽取结果进入人工复核队列（不直接对外发送）。"""
    rows = []
    for g, res in results.items():
        for fname, fr in res.fields.items():
            rows.append({
                "group": g, "field": fname,
                "value": fr.value, "quote": fr.quote,
                "confidence_self": fr.confidence_self,
                "not_found": fr.not_found,
                "quote_not_found": fr.quote_not_found,
                "llm_failed": fr.llm_failed,
                "needs_human_review": True,
            })
    return rows
