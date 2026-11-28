"""5 个字段分组的提示词模板与版本管理。

prompt_version 规则（写入 README）：
- 主版本 MAJOR：字段集合或输出 Schema 变化时 +1；
- 次版本 MINOR：措辞/示例调整（不影响 Schema）时 +0.1；
- 版本随每次调用写入 store.call_log，可在数据库查到。
"""
from __future__ import annotations
from typing import Dict

FIELD_GROUPS: Dict[str, Dict] = {
    "subject": {
        "label": "主体信息",
        "system": "你是合同字段定位与抄录助手。只从原文定位并抄录，不计算、不改写。",
        "fields": ["party_a", "party_b", "contract_name"],
        "instruction": "定位甲方名称(party_a)、乙方名称(party_b)、合同名称(contract_name)。",
    },
    "term": {
        "label": "期限",
        "system": "你是合同字段定位与抄录助手。只从原文定位并抄录，不计算、不改写。",
        "fields": ["effective_date", "expiry_date", "term_desc"],
        "instruction": "定位生效日(effective_date)、到期日(expiry_date)、期限描述(term_desc)。",
    },
    "amount_payment": {
        "label": "金额与付款",
        "system": "你是合同字段定位与抄录助手。只定位与抄录原文片段，禁止计算或换算任何金额。",
        "fields": ["total_amount_quote", "payment_terms_quote"],
        "instruction": "定位总金额原文片段(total_amount_quote)与付款条款原文片段(payment_terms_quote)。金额数值由程序解析，你只抄录。",
    },
    "rights": {
        "label": "权益",
        "system": "你是合同字段定位与抄录助手。只从原文定位并抄录，不计算、不改写。",
        "fields": ["member_rights", "service_scope"],
        "instruction": "定位会员权益描述(member_rights)与服务范围描述(service_scope)。",
    },
    "clauses": {
        "label": "条款摘要",
        "system": "你是合同字段定位与抄录助手。只从原文定位并抄录，不计算、不改写。",
        "fields": ["termination_clause", "liability_clause", "dispute_clause"],
        "instruction": "定位解除条款(termination_clause)、违约责任(liability_clause)、争议解决(dispute_clause)原文片段。",
    },
}

PROMPT_VERSIONS: Dict[str, str] = {
    "subject": "1.1",
    "term": "1.1",
    "amount_payment": "1.1",
    "rights": "1.1",
    "clauses": "1.1",
}


def render_prompt(group: str, structure: Dict, text: str) -> str:
    """渲染某分组提示词。structure 提供字段说明（组名->字段->说明）。"""
    g = FIELD_GROUPS[group]
    lines = [g["system"], "", f"任务分组：{g['label']}（prompt_version={PROMPT_VERSIONS[group]}）", g["instruction"], ""]
    gs = structure.get(group) or {}
    for fname in g["fields"]:
        desc = gs.get(fname, fname)
        lines.append(f"- {fname}: {desc}")
    lines += [
        "",
        "输出 JSON：{\"fields\": {字段名: [{\"value\": 抄录值, \"quote\": 原文连续片段(4-200字), "
        "\"confidence_self\": 0~1, \"not_found\": 该字段是否未在原文找到(true/false)}]}}。"
        "找不到的字段给空列表。quote 必须逐字来自原文。",
    ]
    lines += ["", "【原文】", text or ""]
    return "\n".join(lines)
