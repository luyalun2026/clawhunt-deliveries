# -*- coding: utf-8 -*-
"""虚构数据种子：2 个机构、3 个会所、每会所 3 类账号、7 类资源各 3 条，另加软删除 2 条。

所有名称与编号均为虚构，用于越权测试；不包含任何真实企业或个人信息。
"""
import json
import os
import uuid

ORG_A = {"id": "org_alpha", "name": "示例机构甲"}
ORG_B = {"id": "org_beta", "name": "示例机构乙"}

SITES = [
    {"id": "site_a1", "org_id": "org_alpha", "name": "示例一号会所"},
    {"id": "site_a2", "org_id": "org_alpha", "name": "示例二号会所"},
    {"id": "site_b1", "org_id": "org_beta", "name": "示例一号会所"},
]

RESOURCES = [
    "member_company", "contact", "event", "venue_booking",
    "sop_instance", "opportunity", "kb_article",
]


def actor_id(kind, site):
    return f"{kind}_{site}"


def build_users():
    users = {}
    for s in SITES:
        sid = s["id"]
        users[actor_id("staff", sid)] = {
            "id": actor_id("staff", sid), "role": "staff",
            "site_id": sid, "org_id": s["org_id"], "name": f"会所员工({sid})",
        }
        users[actor_id("admin", sid)] = {
            "id": actor_id("admin", sid), "role": "site_admin",
            "site_id": sid, "org_id": s["org_id"], "name": f"会所管理员({sid})",
        }
    for org in (ORG_A, ORG_B):
        aid = f"hq_{org['id'].split('_')[1]}"
        users[aid] = {
            "id": aid, "role": "hq_admin",
            "site_id": None, "org_id": org["id"], "name": f"总部管理员({org['id']})",
        }
    return users


def build_rows():
    rows = []
    for res in RESOURCES:
        for s in SITES:
            for n in range(1, 4):
                rows.append({
                    "id": f"{res[:3]}-{s['id']}-{n}",
                    "resource": res,
                    "org_id": s["org_id"],
                    "site_id": s["id"],
                    "name": f"{s['name']}·{res}·{n}",
                    "deleted_at": None,
                    "amount_cents": 100000 * n,
                })
    # 每资源各 2 条软删除记录（org_alpha/site_a1）
    for res in RESOURCES:
        rows.append({
            "id": f"{res[:3]}-site_a1-del",
            "resource": res,
            "org_id": "org_alpha",
            "site_id": "site_a1",
            "name": f"示例一号会所·{res}·已删除",
            "deleted_at": "2026-11-01T00:00:00Z",
            "amount_cents": 0,
        })
    return rows


def build_relations():
    """关联关系：contact->member_company、event->venue_booking、sop_instance->template、opportunity->member_company"""
    rel = {}
    for s in SITES:
        sid = s["id"]
        rel[f"con-{sid}-1"] = {"member_company_id": f"mem-{sid}-1"}
        rel[f"eve-{sid}-1"] = {"venue_booking_id": f"ven-{sid}-1"}
        rel[f"sop-{sid}-1"] = {"template_id": f"kb_-{sid}-1"}
        rel[f"opp-{sid}-1"] = {"member_company_id": f"mem-{sid}-2"}
    return rel


def dump(path="seed.json"):
    data = {
        "orgs": [ORG_A, ORG_B],
        "sites": SITES,
        "users": build_users(),
        "rows": build_rows(),
        "relations": build_relations(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return data


if __name__ == "__main__":
    d = dump(os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed.json"))
    print("users", len(d["users"]), "rows", len(d["rows"]))
