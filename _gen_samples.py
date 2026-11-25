#!/usr/bin/env python3
"""生成 valid/ 与 errors/ 样例模板（7 类错误各 1 个）。运行一次即可。"""
import json, os, copy

ROOT = os.path.dirname(os.path.abspath(__file__))

BASE = {
    "template_id": "membership_renewal_v1",
    "name": "会籍续约跟进 SOP",
    "version": "1.0",
    "trigger": {"event": "membership.expiring"},
    "output_form": {"fields": [
        {"field": "contact_reached", "type": "boolean", "required": True},
        {"field": "renewal_intent", "type": "enum", "options": ["yes", "no", "later"], "required": False}
    ]},
    "steps": [
        {"seq": 1, "name": "电话回访", "action": "拨打会员企业联系人电话", "role_code": "service_agent",
         "due_rule": "event.membership.expiring+3d",
         "check_items": [{"text": "已确认联系人身份", "must_pass": True}]},
        {"seq": 2, "name": "续约报价", "action": "发送续约方案与报价单", "role_code": "cc_specialist",
         "due_rule": "created_at+1d", "depends_on": [1],
         "condition": {"field": "contact_reached", "op": "eq", "value": True}}
    ],
    "assets": [{"kind": "knowledge", "ref": "kb_renewal_playbook"}]
}


def mutate(**changes):
    t = copy.deepcopy(BASE)
    for k, v in changes.items():
        if k == "_steps":
            t["steps"] = v
        elif k == "_trigger":
            t["trigger"] = v
        else:
            t[k] = v
    return t


def _step(base_steps, idx, keep_dep=False, **changes):
    s = copy.deepcopy(base_steps[idx])
    s.update(changes)
    if not keep_dep:
        s.pop("depends_on", None)
    return s


b = copy.deepcopy(BASE)["steps"]
samples = {
    "valid_renewal.json": copy.deepcopy(BASE),
    "01_schema_invalid.json": mutate(name=None),
    "02_role_unknown.json": mutate(_steps=[_step(b, 0, role_code="ghost_role"), b[1]]),
    "03_due_rule_invalid.json": mutate(_steps=[_step(b, 0, due_rule="3天后"), b[1]]),
    "04_seq_duplicate.json": mutate(_steps=[b[0], _step(b, 1, seq=1)]),
    "05_trigger_unknown.json": mutate(_trigger={"event": "ghost.event.fired"}),
    "06_depends_on_cycle.json": mutate(_steps=[
        {"seq": 1, "name": "a", "action": "动作一", "role_code": "service_agent", "due_rule": "created_at+1d", "depends_on": [2]},
        {"seq": 2, "name": "b", "action": "动作二", "role_code": "cc_specialist", "due_rule": "created_at+1d", "depends_on": [1]},
    ]),
    "07_condition_field_unknown.json": mutate(_steps=[b[0], _step(b, 1, condition={"field": "ghost_field", "op": "eq", "value": 1})]),
}

for name, tpl in samples.items():
    sub = "valid" if name == "valid_renewal.json" else "errors"
    d = os.path.join(ROOT, sub)
    os.makedirs(d, exist_ok=True)
    json.dump(tpl, open(os.path.join(d, name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", sub + "/" + name)
