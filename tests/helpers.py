# -*- coding: utf-8 -*-
"""测试辅助：身份/对象 id 推导、写路由枚举、请求头。"""
from fixtures import data

ORG = {"a": data.ORG_A, "b": data.ORG_B}
SITE = {"a": ["site-a1", "site-a2"], "b": ["site-b1", "site-b2"]}


def user(org="a", site=1, who="c1"):
    """who: sup | c1 | c2 | c3"""
    org_id = ORG[org]
    site_id = SITE[org][site - 1]
    if who == "sup":
        return data.oid("%s-%s-sup" % (org_id, site_id))
    return data.oid("%s-%s-%s" % (org_id, site_id, who))


def fin(org="a"):
    return data.oid("fin-%s" % org)


def obj_id(kind, owner_id):
    prefix = {"lead": "lead-", "followup": "fu-", "visit": "visit-",
              "quote": "quote-", "contract": "contract-", "attachment": "att-"}[kind]
    return data.oid(prefix + owner_id)


KINDS = ("lead", "followup", "visit", "quote", "contract", "attachment")


def H(actor_id):
    return {"X-Actor-Id": actor_id}


def fill_path(path, owner_id):
    """把 OpenAPI 模板中的路径参数替换成 owner 名下的真实 id。"""
    if "{lead_id}" in path:
        path = path.replace("{lead_id}", obj_id("lead", owner_id))
    if "{item_id}" in path:
        for kind in ("followup", "visit", "quote", "contract", "attachment"):
            if "/%ss/" % kind in path or "/%s/" % kind in path:
                path = path.replace("{item_id}", obj_id(kind, owner_id))
                break
        else:
            path = path.replace("{item_id}", obj_id("lead", owner_id))
    return path


def write_routes(app):
    """从 OpenAPI 文档枚举 /api/sales/ 下全部写路由。"""
    out = []
    for path, ops in app.openapi()["paths"].items():
        if not path.startswith("/api/sales/"):
            continue
        for method in ops:
            if method.upper() in ("POST", "PUT", "PATCH"):
                out.append((method.upper(), path))
    return sorted(out)


def sales_routes(app):
    out = []
    for path, ops in app.openapi()["paths"].items():
        if not path.startswith("/api/sales/"):
            continue
        for method in ops:
            if method.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                out.append((method.upper(), path))
    return sorted(out)
