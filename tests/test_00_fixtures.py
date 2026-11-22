# -*- coding: utf-8 -*-
"""夹具自检：2 org × 2 会所 × (1 主管 + 3 顾问) = 16 人；金额由引擎计算。"""
from app.money import compute_amounts
from fixtures import data
from tests.helpers import ORG, SITE


def test_sixteen_site_users_two_orgs_two_sites_each():
    users = data.build_users()
    assert len(users) == 16
    for org in ("a", "b"):
        org_users = [u for u in users if u["org_id"] == ORG[org]]
        assert len(org_users) == 8
        for site_id in SITE[org]:
            site_users = [u for u in org_users if u["site_id"] == site_id]
            assert len(site_users) == 4
            roles = sorted(u["role"] for u in site_users)
            assert roles == ["consultant", "consultant", "consultant", "supervisor"]


def test_user_ids_unique_and_org_scoped():
    users = data.build_users()
    assert len({u["id"] for u in users}) == 16
    for u in users:
        assert u["org_id"] in SITE_ORGS
        assert u["site_id"] in sum(SITE.values(), [])


SITE_ORGS = {ORG["a"], ORG["b"]}


def test_finance_approvers_are_org_level():
    fin = data.build_finance()
    assert len(fin) == 2
    assert {f["org_id"] for f in fin} == {ORG["a"], ORG["b"]}
    assert all(f["site_id"] is None and f["role"] == "finance" for f in fin)


def test_each_consultant_owns_all_six_object_types(db):
    cons = [u for u in db["users"].values() if u["role"] == "consultant"]
    assert len(cons) == 12
    for c in cons:
        for coll in ("leads", "followups", "visits", "quotes", "contracts", "attachments"):
            owned = [o for o in db[coll].values()
                     if o["owner_id"] == c["id"] and o["org_id"] == c["org_id"]]
            assert len(owned) == 1, (coll, c["id"])


def test_quote_amounts_equal_engine_result(db):
    for q in db["quotes"].values():
        expect = compute_amounts(q["unit_type"], q["concession_bps"], q["lease_months"])
        assert q["final_monthly_cents"] == expect["final_monthly_cents"]
        assert q["deposit_cents"] == expect["deposit_cents"]
        assert q["contract_total_cents"] == expect["contract_total_cents"]
        assert q["first_year_amount_cents"] == expect["first_year_amount_cents"]
