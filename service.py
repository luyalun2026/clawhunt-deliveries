# -*- coding: utf-8 -*-
"""会员空间平台 · 多会所数据隔离的参考实现（接口桩）。

用途：作为越权测试的「被测服务」。实现里刻意把鉴权与数据范围收敛到两处
（scope_sites / writable_sites），这样矩阵即规格：矩阵写 allow 就必须 200，
写 deny 就必须 403/404，写 filtered 就必须「200 但结果集不含范围外数据」。

真实环境把 request() 换成 HTTP 调用即可；测试用环境变量 BASE_URL 切换。
"""
import csv
import io
import json

from seed import build_rows, build_relations, build_users

RESOURCES = [
    "member_company", "contact", "event", "venue_booking",
    "sop_instance", "opportunity", "kb_article",
]

RELATION_FIELDS = {
    "contact": {"member_company": "member_company_id"},
    "event": {"venue_booking": "venue_booking_id"},
    "sop_instance": {"kb_article": "template_id"},
    "opportunity": {"member_company": "member_company_id"},
}


class Service:
    def __init__(self):
        self.users = build_users()
        self.rows = build_rows()
        self.relations = build_relations()
        self.sites = {
            "site_a1": "org_alpha", "site_a2": "org_alpha", "site_b1": "org_beta",
        }
        self.audit = []

    # ---------- 鉴权与数据范围（唯一的规则出口） ----------
    def _user(self, token):
        if not token:
            return None
        return self.users.get(token.replace("Bearer ", "").strip())

    def scope_sites(self, user):
        if user["role"] == "hq_admin":
            return {s for s, o in self.sites.items() if o == user["org_id"]}
        return {user["site_id"]}

    def writable_sites(self, user):
        if user["role"] == "hq_admin":
            return {s for s, o in self.sites.items() if o == user["org_id"]}
        return {user["site_id"]}

    # ---------- 查询辅助 ----------
    def _rows(self, resource, include_deleted=False):
        return [
            r for r in self.rows
            if r["resource"] == resource and (include_deleted or not r["deleted_at"])
        ]

    def _by_id(self, resource, rid):
        for r in self.rows:
            if r["resource"] == resource and r["id"] == rid:
                return r
        return None

    # ---------- 入口 ----------
    def request(self, method, path, token=None, query=None, body=None, headers=None):
        query = query or {}
        headers = headers or {}
        user = self._user(token)
        self.audit.append({"method": method, "path": path, "user": user["id"] if user else None,
                           "query": query, "headers": {k: v for k, v in headers.items()
                                                       if k.lower() in ("x-site-id", "x-org-id")}})
        if user is None:
            return 401, {"code": "UNAUTHENTICATED", "message": "缺少或无效凭证", "request_id": "r-401"}

        parts = [p for p in path.split("/") if p]
        # /api/export
        if parts[:2] == ["api", "export"]:
            return self._export(user, query)
        if len(parts) < 2 or parts[0] != "api":
            return 404, {"code": "NOT_FOUND", "message": "路径不存在", "request_id": "r-404"}
        resource = parts[1]
        if resource not in RESOURCES:
            return 404, {"code": "NOT_FOUND", "message": "资源不存在", "request_id": "r-404"}

        if method == "GET" and len(parts) == 2:
            return self._list(user, resource, query)
        if method == "GET" and len(parts) == 3:
            return self._detail(user, resource, parts[2], query)
        if method == "GET" and len(parts) == 4:
            return self._related(user, resource, parts[2], parts[3])
        if method == "POST" and len(parts) == 2:
            return self._create(user, resource, body or {}, headers)
        return 405, {"code": "METHOD_NOT_ALLOWED", "message": "方法不支持", "request_id": "r-405"}

    # ---------- 行为 ----------
    def _list(self, user, resource, query):
        scope = self.scope_sites(user)
        rows = [r for r in self._rows(resource) if r["site_id"] in scope]
        requested = query.get("site_id")
        if requested:
            # 显式请求范围外会所：只返回范围内容（filtered），绝不回退成全量
            rows = [r for r in rows if r["site_id"] == requested]
        try:
            page = max(1, int(query.get("page", 1)))
            size = int(query.get("page_size", 50))
        except (TypeError, ValueError):
            return 400, {"code": "BAD_REQUEST", "message": "分页参数非法", "request_id": "r-400"}
        if size > 200:
            size = 200
        start = (page - 1) * size
        window = rows[start:start + size]
        return 200, {
            "code": "OK", "message": "ok", "request_id": "r-list",
            "total": len(rows), "page": page, "page_size": size,
            "items": [self._public(r) for r in window],
        }

    def _detail(self, user, resource, rid, query):
        row = self._by_id(resource, rid)
        scope = self.scope_sites(user)
        if row is None:
            return 404, {"code": "NOT_FOUND", "message": "不存在", "request_id": "r-404"}
        if row["site_id"] not in scope:
            return 404, {"code": "NOT_FOUND", "message": "不存在", "request_id": "r-404"}
        if row["deleted_at"] and not (user["role"] == "hq_admin" and query.get("include_deleted") == "1"):
            return 404, {"code": "NOT_FOUND", "message": "不存在", "request_id": "r-404"}
        return 200, {"code": "OK", "message": "ok", "request_id": "r-detail", "item": self._public(row)}

    def _related(self, user, resource, rid, rel):
        field = RELATION_FIELDS.get(resource, {}).get(rel)
        if not field:
            return 404, {"code": "NOT_FOUND", "message": "关联不存在", "request_id": "r-404"}
        row = self._by_id(resource, rid)
        if row is None or row["site_id"] not in self.scope_sites(user):
            return 404, {"code": "NOT_FOUND", "message": "不存在", "request_id": "r-404"}
        rel_map = self.relations.get(rid) or {}
        target_id = rel_map.get(field)
        if not target_id:
            return 404, {"code": "NOT_FOUND", "message": "未关联", "request_id": "r-404"}
        target = self._by_id(rel, target_id) if rel != "kb_article" else self._by_id("kb_article", target_id)
        if target is None or target["site_id"] not in self.scope_sites(user):
            # 关联目标越界必须拒绝，不能因为「主对象可见」就放行
            return 404, {"code": "NOT_FOUND", "message": "不存在", "request_id": "r-404"}
        return 200, {"code": "OK", "message": "ok", "request_id": "r-rel", "item": self._public(target)}

    def _create(self, user, resource, body, headers):
        writable = self.writable_sites(user)
        # header 里的 site 只能作为提示，不参与鉴权
        site = body.get("site_id")
        if not site:
            return 400, {"code": "BAD_REQUEST", "message": "缺少 site_id", "request_id": "r-400"}
        if site not in writable:
            return 403, {"code": "FORBIDDEN", "message": "无该会所写权限", "request_id": "r-403"}
        new = {
            "id": f"{resource[:3]}-{site}-new{len([r for r in self.rows if r['resource'] == resource])}",
            "resource": resource, "org_id": self.sites[site], "site_id": site,
            "name": body.get("name", "新建对象"), "deleted_at": None,
            "amount_cents": int(body.get("amount_cents") or 0),
        }
        self.rows.append(new)
        return 201, {"code": "OK", "message": "created", "request_id": "r-create", "item": self._public(new)}

    def _export(self, user, query):
        resource = query.get("resource")
        if resource not in RESOURCES:
            return 400, {"code": "BAD_REQUEST", "message": "resource 非法", "request_id": "r-400"}
        scope = self.scope_sites(user)
        rows = [r for r in self._rows(resource) if r["site_id"] in scope]
        requested = query.get("site_id")
        if requested:
            rows = [r for r in rows if r["site_id"] == requested]
        ids = query.get("ids")
        if ids:
            wanted = {x for x in ids.split(",") if x}
            rows = [r for r in rows if r["id"] in wanted]
        fmt = query.get("format", "json")
        if fmt == "csv":
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["id", "resource", "org_id", "site_id", "name"])
            for r in rows:
                w.writerow([r["id"], r["resource"], r["org_id"], r["site_id"], r["name"]])
            return 200, {"code": "OK", "message": "ok", "request_id": "r-export",
                         "format": "csv", "content": buf.getvalue(), "count": len(rows)}
        return 200, {"code": "OK", "message": "ok", "request_id": "r-export",
                     "format": "json", "count": len(rows),
                     "items": [self._public(r) for r in rows]}

    @staticmethod
    def _public(row):
        return {"id": row["id"], "org_id": row["org_id"], "site_id": row["site_id"],
                "name": row["name"], "amount_cents": row["amount_cents"]}


if __name__ == "__main__":
    s = Service()
    code, body = s.request("GET", "/api/member_company", token="staff_site_a1")
    print(code, json.dumps(body, ensure_ascii=False)[:200])
