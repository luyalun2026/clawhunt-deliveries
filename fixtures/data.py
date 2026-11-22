# -*- coding: utf-8 -*-
"""虚构测试数据夹具：2 个 org × 每个 org 2 个会所 × 每个会所（1 名主管 + 3 名顾问）= 16 人。

另设 2 名 org 级财务审批人（审批流第二步的角色持有者，不属于 4 人会所编制）。
所有企业名、人名、手机号均为虚构，不含任何真实个人信息。
"""
import uuid

from app.money import compute_amounts

_NS = uuid.UUID("11111111-2222-3333-4444-555555555555")


def oid(name):
    """稳定 UUID（同一 name 每次生成相同 id，便于断言与复现）。"""
    return str(uuid.uuid5(_NS, name))


ORG_A, ORG_B = oid("org-a"), oid("org-b")

SITES = {
    ORG_A: [("site-a1", "会所甲一"), ("site-a2", "会所甲二")],
    ORG_B: [("site-b1", "会所乙一"), ("site-b2", "会所乙二")],
}

_SURNAMES = ["赵", "钱", "孙", "李", "周", "吴", "郑", "王"]
_GIVEN = ["一", "二", "三", "四"]


def build_users():
    users = []
    for org_id, sites in SITES.items():
        n = 0
        for site_index, (site_id, site_name) in enumerate(sites, start=1):
            sup_id = oid("%s-%s-sup" % (org_id, site_id))
            users.append({
                "id": sup_id, "org_id": org_id, "site_id": site_id,
                "role": "supervisor", "name": "主管-%s-%d" % (site_name, site_index),
                "phone": "1390000%04d" % (n + 1), "site_name": site_name,
            })
            for c in range(1, 4):
                uid = oid("%s-%s-c%d" % (org_id, site_id, c))
                users.append({
                    "id": uid, "org_id": org_id, "site_id": site_id,
                    "role": "consultant",
                    "name": "顾问-%s-%s" % (_SURNAMES[n % len(_SURNAMES)], _GIVEN[c - 1]),
                    "phone": "1380000%04d" % (n * 3 + c), "site_name": site_name,
                })
                n += 1
    return users


def build_finance():
    return [
        {"id": oid("fin-a"), "org_id": ORG_A, "site_id": None, "role": "finance",
         "name": "财务审批-甲", "phone": "13700000001", "site_name": None},
        {"id": oid("fin-b"), "org_id": ORG_B, "site_id": None, "role": "finance",
         "name": "财务审批-乙", "phone": "13700000002", "site_name": None},
    ]


def _quote_amounts(unit_type, concession_bps, lease_months):
    a = compute_amounts(unit_type, concession_bps, lease_months)
    return {
        "final_monthly_cents": a["final_monthly_cents"],
        "deposit_cents": a["deposit_cents"],
        "contract_total_cents": a["contract_total_cents"],
        "first_year_amount_cents": a["first_year_amount_cents"],
    }


def build_db():
    users = build_users()
    finance = build_finance()
    db = {"users": {u["id"]: dict(u) for u in users + finance},
          "orgs": {}, "sites": {}, "leads": {}, "followups": {}, "visits": {},
          "quotes": {}, "contracts": {}, "attachments": {}, "esign_events": []}

    for org_id, sites in SITES.items():
        db["orgs"][org_id] = {"id": org_id, "name": "虚构会员空间集团-%s" % org_id[-1].upper()}
        for site_id, site_name in sites:
            db["sites"][site_id] = {"id": site_id, "org_id": org_id, "name": site_name}

    for u in users:
        if u["role"] != "consultant":
            continue
        uid, org_id, site_id = u["id"], u["org_id"], u["site_id"]
        # 每个顾问各持有 6 类对象各 1 条，便于逐个 id 做越权探测
        lead_id = oid("lead-" + uid)
        db["leads"][lead_id] = {
            "id": lead_id, "org_id": org_id, "site_id": site_id, "owner_id": uid,
            "created_by": uid, "name": "线索-%s" % u["name"], "company": "虚构企业-%s" % uid[:6],
            "phone": "1380000%04d" % (abs(hash(uid)) % 10000), "status": "following",
            "source": "公域投放", "budget_cents": 0,
        }
        db["followups"][oid("fu-" + uid)] = {
            "id": oid("fu-" + uid), "org_id": org_id, "site_id": site_id, "owner_id": uid,
            "created_by": uid, "lead_id": lead_id, "channel": "电话",
            "note": "虚构跟进记录（第 1 次）",
        }
        db["visits"][oid("visit-" + uid)] = {
            "id": oid("visit-" + uid), "org_id": org_id, "site_id": site_id, "owner_id": uid,
            "created_by": uid, "lead_id": lead_id, "visit_at": "2026-12-01T10:00:00+08:00",
            "status": "planned",
        }
        q_amounts = _quote_amounts("office", 0, 24)
        quote_id = oid("quote-" + uid)
        db["quotes"][quote_id] = {
            "id": quote_id, "org_id": org_id, "site_id": site_id, "owner_id": uid,
            "created_by": uid, "lead_id": lead_id, "unit_type": "office",
            "lease_months": 24, "concession_bps": 0, "status": "draft",
            "approval_steps": [{"role": "supervisor", "status": "pending", "decided_by": None},
                               {"role": "finance", "status": "pending", "decided_by": None}],
            "current_step": 0,
            **q_amounts,
        }
        db["contracts"][oid("contract-" + uid)] = {
            "id": oid("contract-" + uid), "org_id": org_id, "site_id": site_id, "owner_id": uid,
            "created_by": uid, "quote_id": quote_id, "status": "draft",
            "signed_at": None, "esign_ref": None,
            "contract_total_cents": q_amounts["contract_total_cents"],
        }
        db["attachments"][oid("att-" + uid)] = {
            "id": oid("att-" + uid), "org_id": org_id, "site_id": site_id, "owner_id": uid,
            "created_by": uid, "quote_id": quote_id, "filename": "报价单-%s.pdf" % uid[:6],
            "content_type": "application/pdf", "size_bytes": 20480,
        }

    # 公海线索：无归属，任何本 org 顾问可见，但手机号必须脱敏
    for i, org_id in enumerate([ORG_A, ORG_B], start=1):
        site_id = SITES[org_id][0][0]
        pid = oid("pool-%d" % i)
        db["leads"][pid] = {
            "id": pid, "org_id": org_id, "site_id": site_id, "owner_id": None,
            "created_by": None, "name": "公海线索-%d" % i, "company": "虚构公海企业-%d" % i,
            "phone": "1381234%04d" % (1000 + i), "status": "public", "source": "展会",
            "budget_cents": 0,
        }
    return db


def consultant_ids(db):
    return [u["id"] for u in db["users"].values() if u["role"] == "consultant"]
