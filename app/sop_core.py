# -*- coding: utf-8 -*-
"""sop_core — SOP 模板校验、导入导出、lint 的纯函数核心（供 CLI 与 API 复用）。"""
from __future__ import annotations
import json, os, re

import jsonschema

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schema", "sop-template.schema.json")

DUE_RULE_RE = re.compile(r"^(created_at\+\d+d|event\.[a-z0-9_.]+\+\d+d)$")


def load_schema() -> dict:
    return json.load(open(SCHEMA_PATH, encoding="utf-8"))


def load_catalogs(path: str | None = None) -> dict:
    if path is None:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "catalogs", "catalogs.json")
    return json.load(open(path, encoding="utf-8"))


# ---------------- lint ----------------

def lint_template(tpl: dict, catalogs: dict) -> list[dict]:
    """返回错误列表：[{rule, message, path}]。空列表 = 全绿。"""
    errors: list[dict] = []

    def err(rule, message, path):
        errors.append({"rule": rule, "message": message, "path": path})

    # 1. Schema 校验
    try:
        jsonschema.validate(tpl, load_schema())
    except jsonschema.ValidationError as e:
        err("schema_invalid", e.message, ".".join(str(p) for p in e.absolute_path) or "(root)")
        return errors  # schema 不过，后续检查无意义

    role_codes = {r["code"] for r in catalogs["roles"]}
    doc_codes = {d["code"] for d in catalogs["knowledge_docs"]}
    event_codes = {e["code"] for e in catalogs["event_types"]}
    form_fields = {f["field"] for f in (tpl.get("output_form") or {}).get("fields", [])}

    steps = tpl.get("steps", [])
    seqs = [s["seq"] for s in steps]

    # 4. seq 重复 / 负数（schema 已挡负数，这里挡重复）
    if len(seqs) != len(set(seqs)):
        err("seq_duplicate", f"步骤 seq 重复: {[x for x in seqs if seqs.count(x) > 1]}", "steps")

    by_seq = {s["seq"]: s for s in steps}
    for s in steps:
        path = f"steps[seq={s['seq']}]"

        # 2. 岗位编码存在
        if s["role_code"] not in role_codes:
            err("role_unknown", f"岗位编码 {s['role_code']} 不在岗位目录", path + ".role_code")

        # 3. due_rule 合法（schema pattern 为主，二次防御）
        if not DUE_RULE_RE.match(s["due_rule"]):
            err("due_rule_invalid", f"due_rule 非法: {s['due_rule']}", path + ".due_rule")

        # 6. depends_on 成环（含自环）
        for dep in s.get("depends_on", []):
            if dep == s["seq"]:
                err("depends_on_cycle", f"步骤 {s['seq']} depends_on 自身", path + ".depends_on")
            elif dep not in by_seq:
                err("depends_on_missing", f"depends_on 引用不存在的 seq={dep}", path + ".depends_on")
        if s.get("depends_on") and dep not in (s["seq"],) and dep in by_seq:
            pass  # 环检测统一在下方 DFS 做

        # 7. 条件表达式字段路径合法（须指向 output_form 已声明字段）
        cond = s.get("condition") or (tpl.get("trigger") or {}).get("condition")
        if cond:
            root = cond["field"].split(".")[0]
            if cond["field"] not in form_fields and root not in form_fields:
                err("condition_field_unknown", f"条件字段 {cond['field']} 不在输出表单字段集", path + ".condition.field")

    # 6b. depends_on 环检测（DFS）
    graph = {s["seq"]: [d for d in s.get("depends_on", []) if d in by_seq] for s in steps}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in graph}

    def dfs(n, stack):
        color[n] = GRAY
        for m in graph.get(n, []):
            if color.get(m) == GRAY:
                err("depends_on_cycle", f"depends_on 成环: {stack + [n, m]}", "steps")
            elif color.get(m) == WHITE:
                dfs(m, stack + [n])
        color[n] = BLACK

    for n in graph:
        if color[n] == WHITE:
            dfs(n, [])

    # 5. 触发事件属于事件目录
    trigger = tpl.get("trigger") or {}
    if trigger.get("event") and trigger["event"] not in event_codes:
        err("trigger_event_unknown", f"触发事件 {trigger['event']} 不在事件目录", "trigger.event")

    return errors


# ---------------- 导入（draft） ----------------

def import_template(payload: dict, catalogs: dict, store: dict) -> dict:
    """导入为草稿：解析不到的引用进 warnings，模板照常落草稿。返回响应 dict。"""
    warnings: list[dict] = []
    role_codes = {r["code"] for r in catalogs["roles"]}
    doc_codes = {d["code"] for d in catalogs["knowledge_docs"]}
    event_codes = {e["code"] for e in catalogs["event_types"]}

    for s in payload.get("steps", []):
        if s.get("role_code") not in role_codes:
            warnings.append({"field": f"steps[seq={s.get('seq')}].role_code", "code": s.get("role_code"), "reason": "岗位编码不在目录"})
    for a in payload.get("assets", []):
        if a.get("kind") == "knowledge" and a.get("ref") not in doc_codes:
            warnings.append({"field": f"assets[ref={a.get('ref')}]", "code": a.get("ref"), "reason": "知识文档编码不在目录"})
    trig = payload.get("trigger") or {}
    if trig.get("event") and trig["event"] not in event_codes:
        warnings.append({"field": "trigger.event", "code": trig["event"], "reason": "事件类型不在目录"})

    tid = payload["template_id"]
    store[tid] = {"status": "draft", "template": payload, "warnings": warnings}
    return {"template_id": tid, "status": "draft", "warnings": warnings}


# ---------------- 导出 ----------------

RUNTIME_META_KEYS = {"exported_at", "exported_by"}


def export_template(tid: str, store: dict, exported_by: str = "system") -> dict | None:
    if tid not in store:
        return None
    tpl = json.loads(json.dumps(store[tid]["template"]))  # 深拷贝
    tpl["meta"] = {"exported_at": "2026-01-01T00:00:00Z", "exported_by": exported_by}
    return tpl


def strip_runtime(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in RUNTIME_META_KEYS and k != "meta"}
