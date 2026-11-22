# -*- coding: utf-8 -*-
"""生成 access_matrix.yaml（JSON 兼容的 YAML 子集，避免引入 PyYAML 依赖）。

矩阵维度：7 类资源 × 3 类账号 × 5 个场景 = 105 格，每格显式写 allow / deny / filtered。
不写缺省值——缺省值是「假通过」的主要来源，脚本会断言空格数为 0。
"""
import json
import os

RESOURCES = [
    "member_company", "contact", "event", "venue_booking",
    "sop_instance", "opportunity", "kb_article",
]

SCENARIOS = ["own_list", "same_org_other_list", "other_org_list", "foreign_detail", "foreign_write"]

RULES = {
    "staff": {
        "own_list": "allow", "same_org_other_list": "filtered",
        "other_org_list": "filtered", "foreign_detail": "deny", "foreign_write": "deny",
    },
    "site_admin": {
        "own_list": "allow", "same_org_other_list": "filtered",
        "other_org_list": "filtered", "foreign_detail": "deny", "foreign_write": "deny",
    },
    "hq_admin": {
        "own_list": "allow", "same_org_other_list": "allow",
        "other_org_list": "filtered", "foreign_detail": "deny", "foreign_write": "deny",
    },
}

DOC = {
    "_note": "JSON 兼容 YAML：本文件同时是合法 JSON，可直接用 json.load 读取；格值仅 allow/deny/filtered。",
    "version": 1,
    "fixtures": {
        "orgs": {"org_alpha": ["site_a1", "site_a2"], "org_beta": ["site_b1"]},
        "actors": {
            "staff": "staff_site_a1", "site_admin": "admin_site_a1", "hq_admin": "hq_alpha",
        },
        "own_site": "site_a1", "same_org_other_site": "site_a2", "other_org_site": "site_b1",
    },
    "scenarios": {
        "own_list": "GET /api/<res>?site_id=site_a1",
        "same_org_other_list": "GET /api/<res>?site_id=site_a2",
        "other_org_list": "GET /api/<res>?site_id=site_b1",
        "foreign_detail": "GET /api/<res>/<site_b1 的对象 id>",
        "foreign_write": "POST /api/<res> body.site_id=site_b1",
    },
    "resources": RESOURCES,
    "cells": {r: {a: dict(RULES[a]) for a in RULES} for r in RESOURCES},
}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "access_matrix.yaml")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(DOC, f, ensure_ascii=False, indent=1)
    total = sum(len(v) for r in DOC["cells"].values() for v in r.values())
    blank = sum(1 for r in DOC["cells"].values() for v in r.values() for x in v.values() if not x)
    print(f"cells={total} blank={blank} resources={len(RESOURCES)} actors={len(RULES)}")
    return total, blank


if __name__ == "__main__":
    main()
