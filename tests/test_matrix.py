# -*- coding: utf-8 -*-
"""矩阵驱动用例：每格一个 testcase，名字里带资源/账号/场景，便于报告定位。"""
import itertools

import pytest

OWN = "site_a1"
SAME_ORG = "site_a2"
OTHER_ORG = "site_b1"


def prefix(resource):
    return resource[:3]


def scope_of(actor_type):
    return {OWN} if actor_type in ("staff", "site_admin") else {OWN, SAME_ORG}


def cell_params():
    from make_matrix import RESOURCES, SCENARIOS, RULES
    for res, actor in itertools.product(RESOURCES, ["staff", "site_admin", "hq_admin"]):
        for sc in SCENARIOS:
            yield res, actor, sc, RULES[actor][sc]


@pytest.mark.parametrize("resource,actor_type,scenario,expected", list(cell_params()))
def test_matrix_cell(svc, resource, actor_type, scenario, expected):
    fx_token = {"staff": "staff_site_a1", "site_admin": "admin_site_a1", "hq_admin": "hq_alpha"}[actor_type]
    scope = scope_of(actor_type)
    if scenario == "own_list":
        code, body = svc.request("GET", f"/api/{resource}", token=fx_token, query={"site_id": OWN})
    elif scenario == "same_org_other_list":
        code, body = svc.request("GET", f"/api/{resource}", token=fx_token, query={"site_id": SAME_ORG})
    elif scenario == "other_org_list":
        code, body = svc.request("GET", f"/api/{resource}", token=fx_token, query={"site_id": OTHER_ORG})
    elif scenario == "foreign_detail":
        code, body = svc.request("GET", f"/api/{resource}/{prefix(resource)}-{OTHER_ORG}-1", token=fx_token)
    elif scenario == "foreign_write":
        code, body = svc.request("POST", f"/api/{resource}", token=fx_token,
                                 body={"name": "越权写入", "site_id": OTHER_ORG})
    else:  # pragma: no cover
        raise AssertionError("未知场景 " + scenario)

    if expected == "allow":
        assert code == 200, f"{resource}/{actor_type}/{scenario} 期望 200，实际 {code} {body}"
        items = body["items"]
        assert items, "期望非空结果集"
        target = {"own_list": OWN, "same_org_other_list": SAME_ORG}[scenario]
        assert all(i["site_id"] == target for i in items)
    elif expected == "filtered":
        assert code == 200, f"{resource}/{actor_type}/{scenario} 期望 200(filtered)，实际 {code}"
        assert all(i["site_id"] in scope for i in body["items"]), "filtered 结果出现范围外数据"
        assert all(i["site_id"] != OTHER_ORG for i in body["items"])
    elif expected == "deny":
        assert code in (403, 404), f"{resource}/{actor_type}/{scenario} 期望 403/404，实际 {code} {body}"
        assert body.get("code") in ("FORBIDDEN", "NOT_FOUND")
    else:  # pragma: no cover
        raise AssertionError("未知期望值 " + expected)
