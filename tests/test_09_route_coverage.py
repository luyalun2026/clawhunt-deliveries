# -*- coding: utf-8 -*-
"""路由覆盖用例：OpenAPI 自动枚举 vs 登记表；演示新增路由即失败。"""
import pytest

from app.main import create_app
from tests.coverage import COVERED
from tests.helpers import sales_routes
from tools.check_route_coverage import enforce, violations

NEW_ROUTE = ("POST", "/api/sales/leads/{lead_id}/restore")


def test_every_sales_route_is_registered(app):
    routes = set(sales_routes(app))
    missing = sorted(routes - set(COVERED))
    stale = sorted(set(COVERED) - routes)
    assert not missing, "未纳入测试的路由: %s" % missing
    assert not stale, "登记表存在已删除路由: %s" % stale
    assert len(routes) == len(COVERED) == 33


def test_registered_coverage_points_to_real_tests(request):
    nodeids = [item.nodeid for item in request.session.items]
    for route, target in COVERED.items():
        assert any(n.startswith(target) for n in nodeids), (route, target)


def test_new_uncovered_route_makes_suite_fail():
    """复现验收项 2：新增一个未纳入测试的路由时，门禁必须报错并使套件失败。"""
    app = create_app()

    @app.post("/api/sales/leads/{lead_id}/restore")
    def restore(lead_id: str):  # pragma: no cover - 仅用于演示门禁
        return {"ok": True}

    missing, stale = violations(app)
    assert missing == [NEW_ROUTE], missing
    assert stale == []
    with pytest.raises(AssertionError) as exc:
        enforce(app)
    assert "restore" in str(exc.value)


def test_removed_route_is_detected_as_stale():
    """路由被删除后，登记表里的旧条目必须被识别为 stale。"""
    extra = dict(COVERED)
    extra[("GET", "/api/sales/legacy-report")] = "tests/test_00_fixtures.py::test_sixteen_site_users_two_orgs_two_sites_each"
    missing, stale = violations(create_app(), extra)
    assert ("GET", "/api/sales/legacy-report") in stale
    assert missing == []
