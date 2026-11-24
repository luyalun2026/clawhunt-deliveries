# -*- coding: utf-8 -*-
"""问题单生成：仅对「实际结果 != 期望行为」的场景出单。

每条问题单必带：涉及表、涉及接口、复现步骤、建议改法。
"""
from __future__ import annotations

from typing import Any

# 场景 → 可能涉及的落点（虚构 schema 名，与工单约定一致）
LOCUS: dict[str, dict[str, list[str] | str]] = {
    "S01": {"tables": ["crm_enterprises", "enterprise_site_relations"],
            "apis": ["GET /api/crm/enterprises", "POST /api/crm/enterprises"],
            "suggest": "在 (org_id, credit_code) 上建唯一索引；入驻走关系表，禁止复制企业主档"},
    "S02": {"tables": ["events", "event_registrations"],
            "apis": ["POST /api/events/{id}/registrations"],
            "suggest": "报名校验只判活动 visibility 与 status，不判 member.site_id"},
    "S03": {"tables": ["contacts", "contact_owner_history"],
            "apis": ["PATCH /api/contacts/{id}/owner"],
            "suggest": "负责人变更写历史表；查询按 owner_id 过滤当前值"},
    "S04": {"tables": ["sites"], "apis": ["PATCH 全部写接口"],
            "suggest": "统一中间件校验 site.status=closed → 409；读接口不受限"},
    "S05": {"tables": ["opportunities", "opportunity_referrals"],
            "apis": ["POST /api/opportunities/{id}/transfer"],
            "suggest": "转介写 referral 记录并改 site_id；A 会所视图脱敏 amount/ent_id"},
    "S06": {"tables": ["kb_articles"], "apis": ["GET /api/kb/articles/{id}"],
            "suggest": "scope=org 时不做 site 过滤"},
    "S07": {"tables": ["kb_articles"], "apis": ["GET /api/kb/articles/{id}"],
            "suggest": "scope=site 时强制 site_id 匹配；不匹配返回 404 而非 403"},
    "S08": {"tables": ["org_dictionaries", "site_dictionaries"],
            "apis": ["GET/PUT /api/dicts/space_type"],
            "suggest": "机构键只读；会所只能追加键，冲突拒绝"},
    "S09": {"tables": ["site_configs", "group_configs"], "apis": ["GET /api/config/{key}"],
            "suggest": "按 site → group 顺序回落，命中即返回"},
    "S10": {"tables": ["（汇总视图）"], "apis": ["GET /api/dashboard/overview"],
            "suggest": "总部查询与单会所查询共用同一 WHERE 构造器，避免口径漂移"},
    "S11": {"tables": ["contacts"], "apis": ["GET 全部列表/导出接口"],
            "suggest": "所有查询统一追加 deleted_at IS NULL；统计口径按需保留"},
    "S12": {"tables": ["contacts"], "apis": ["GET /api/contacts/export"],
            "suggest": "导出复用列表的可见性构造器，禁止独立拼 SQL"},
}


def make_issues(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues = []
    for r in results:
        if r["ok"]:
            continue
        loc = LOCUS.get(r["id"], {"tables": ["待定"], "apis": ["待定"], "suggest": "待定"})
        issues.append({
            "scenario": r["id"],
            "title": r["name"],
            "expected": r["expected"],
            "actual": r["actual"],
            "tables": loc["tables"],
            "apis": loc["apis"],
            "repro": f"python -m app.scenarios --only {r['id']}",
            "suggestion": loc["suggest"],
        })
    return issues


def render_markdown(issues: list[dict[str, Any]]) -> str:
    if not issues:
        return "# 问题单\n\n本轮 12 个场景实际结果与期望行为一致，无待修问题（0 条）。\n"
    lines = ["# 问题单", "", f"共 {len(issues)} 条（每条对应 1 个不一致场景）。", ""]
    for i, it in enumerate(issues, 1):
        lines += [
            f"## {i}. [{it['scenario']}] {it['title']}",
            f"- 期望：{it['expected']}",
            f"- 实际：{it['actual']}",
            f"- 涉及表：{', '.join(it['tables'])}",
            f"- 涉及接口：{', '.join(it['apis'])}",
            f"- 复现：`{it['repro']}`",
            f"- 建议改法：{it['suggestion']}",
            "",
        ]
    return "\n".join(lines)
