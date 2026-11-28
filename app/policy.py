# -*- coding: utf-8 -*-
"""禁答规则：三类（联系方式 / 经营信息 / 价格合同承诺），正则 + 关键词双通道。"""
import os
import re

import yaml

RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "forbidden_rules.yaml")

CATEGORIES = ("contact", "business", "commitment")


class RuleConfigError(ValueError):
    pass


def load_rules(path=RULES_PATH):
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    rules = doc.get("rules") or []
    seen = set()
    for r in rules:
        rid = r.get("id")
        if not rid:
            raise RuleConfigError("规则缺少 id")
        if rid in seen:
            raise RuleConfigError("规则 id 重复：%s" % rid)
        seen.add(rid)
        if r.get("category") not in CATEGORIES:
            raise RuleConfigError("未知类别：%s" % r.get("category"))
        if len(r.get("examples") or []) < 3:
            raise RuleConfigError("类别 %s 的规则 %s 样例不足 3 条" % (r.get("category"), rid))
    for cat in CATEGORIES:
        if not any(r.get("category") == cat for r in rules):
            raise RuleConfigError("缺少类别：%s" % cat)
    return rules


def make_router(rules):
    compiled = []
    for r in rules:
        compiled.append((r["id"], r["category"],
                         re.compile(r["pattern"]) if r.get("pattern") else None,
                         [k for k in (r.get("keywords") or [])]))

    def route(question):
        # 输入防护：截断超长文本、去除控制字符（正则模式来自服务端配置文件，
        # 不来自用户输入，因此无 ReDoS 注入面）
        q = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(question or ""))[:2000]
        for rid, cat, pattern, keywords in compiled:
            if pattern is not None and pattern.search(q):
                return cat
            if keywords and any(k in q for k in keywords):
                return cat
        return None

    route.rules = compiled
    return route
