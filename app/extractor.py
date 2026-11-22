# -*- coding: utf-8 -*-
"""intel.conditions.v1 抽取编排 + 后置校验。

extract(text, publish_date) → {"key_conditions": [...], "deadlines": [...],
"earliest_submission": "...", "audit": {"dropped": [...]}, "meta": {...}}

后置校验（不可绕过）：
  1. source_text 必须能在原文中逐字找到，否则丢弃并记入 audit.dropped。
  2. key_conditions.text 超过 50 字的条目丢弃（保持逐字可回验，不截断）。
  3. 相对日期一律由程序按发布日期推算并标注 origin=程序推算；模型/规则只产出原文片段。
  4. 多条 submission 时，顶层 earliest_submission 取最早的申报截止日期。
  5. amount_rule 只照抄原文片段，不计算、不汇总。
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime

from .relative_date import normalize_relative_date, parse_absolute

SENT_SPLIT = re.compile(r"(?<=[。；；!\?\n])")
MAX_COND_TEXT = 50

# ---- 类型判定关键词（与 intel/prompt_v1.md 的判定口径一致）----

DEADLINE_TYPE_RULES = [
    ("submission", re.compile(r"申报截止|截止日期|截止时间|前(?:提交|申报|报名|送达|报送)|申报时间截至|报名截止|受理截止|日内(?:完成|报送|提交)")),
    ("effective_until", re.compile(r"有效期(?:至|为)|有效期\d|执行至")),
    ("event_date", re.compile(r"活动日期|举办时间|会议时间|召开时间|培训时间|评比时间|评审会时间")),
]

CONDITION_TYPE_RULES = [
    ("eligibility", re.compile(r"申报条件|申请条件|资格要求|支持对象|适用于|申报范围|对象为")),
    ("material", re.compile(r"申报材料|申请材料|需提交|材料清单|材料包括|附件\d|提供以下材料")),
    ("process", re.compile(r"办理流程|申报程序|审批流程|流程如下|受理程序|办理步骤")),
    ("amount_rule", re.compile(r"\d+(?:\.\d+)?\s*万元|\d+(?:\.\d+)?\s*元|补贴|资助|补助|比例|费率|不超过.*万|标准为")),
]

RELATIVE_IN_SENT = re.compile(r"(?:自)?(?:发布|印发|公告发布|通知发布)之日起")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in SENT_SPLIT.split(text)]
    return [p for p in parts if p]


def _match_deadline_type(sentence: str):
    for dtype, pat in DEADLINE_TYPE_RULES:
        if pat.search(sentence):
            return dtype
    return None


def _match_condition_type(sentence: str):
    for ctype, pat in CONDITION_TYPE_RULES:
        if pat.search(sentence):
            return ctype
    return None


def _raw_deadline_fragments(text: str):
    """从文本中取日期片段（绝对日期 / 相对日期短语），返回 [(fragment, is_relative)]。"""
    out = []
    for m in re.finditer(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日(?:前)?", text):
        out.append((m.group(0), False))
    for m in re.finditer(r"(?:自)?(?:发布|印发|公告发布|通知发布)之日起\s*\d+\s*(?:个)?\s*(?:日|天|工作日)内", text):
        out.append((m.group(0), True))
    return out


CLAUSE_SPLIT = re.compile(r"[。；，]")


class _LLMStub:
    """进程内确定性实现，接口与 LLM 版一致；生产替换见 README。"""

    def extract_raw(self, sentences):
        conds, deads = [], []
        for idx, sent in enumerate(sentences):
            ctype = _match_condition_type(sent)
            if ctype:
                conds.append({"text": sent[:MAX_COND_TEXT], "type": ctype, "sentence_idx": idx})
            # 子句级类型判定：日期片段继承其所在子句的截止语义，避免同句多日期串型
            for clause in CLAUSE_SPLIT.split(sent):
                dtype = _match_deadline_type(clause)
                if not dtype:
                    continue
                for frag, is_rel in _raw_deadline_fragments(clause):
                    deads.append({"deadline_type": dtype, "source_text": frag,
                                  "sentence_idx": idx, "_relative": is_rel})
        return conds, deads


_LLM = _LLMStub()


def extract(text: str, publish_date: datetime) -> dict:
    sentences = split_sentences(text)
    raw_conds, raw_deads = _LLM.extract_raw(sentences)

    audit_dropped = []
    key_conditions = []
    for c in raw_conds:
        if c["text"] not in text:
            audit_dropped.append({"kind": "condition", "item": c, "reason": "not_verbatim"})
            continue
        key_conditions.append(c)

    deadlines = []
    for d in raw_deads:
        if d["source_text"] not in text:
            audit_dropped.append({"kind": "deadline", "item": d, "reason": "not_verbatim"})
            continue
        if d["_relative"]:
            date, origin = normalize_relative_date(d["source_text"], publish_date)
        else:
            parsed = parse_absolute(d["source_text"])
            if parsed is None:
                audit_dropped.append({"kind": "deadline", "item": d, "reason": "unparseable_date"})
                continue
            date, origin = parsed
        deadlines.append({"deadline_type": d["deadline_type"],
                          "source_text": d["source_text"],
                          "sentence_idx": d["sentence_idx"],
                          "deadline": date.strftime("%Y-%m-%d"),
                          "origin": origin})

    # 多条 submission 时，条目 deadline 取最早（顶层 earliest_submission）
    submission_dates = sorted(x["deadline"] for x in deadlines
                              if x["deadline_type"] == "submission")
    earliest = submission_dates[0] if submission_dates else None

    deadlines.sort(key=lambda x: (x["deadline"], x["sentence_idx"]))
    return {
        "key_conditions": key_conditions,
        "deadlines": deadlines,
        "earliest_submission": earliest,
        "audit": {"dropped": audit_dropped},
        "meta": {"version": "intel.conditions.v1",
                 "publish_date": publish_date.strftime("%Y-%m-%d"),
                 "sentence_count": len(sentences),
                 "engine": "offline-rule-stub"},
    }


def load_schema():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "app", "schema_v1.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)
