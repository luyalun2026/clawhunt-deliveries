# -*- coding: utf-8 -*-
"""路由覆盖登记表：OpenAPI 枚举出的每条 /api/sales/ 路由都必须在此登记，
并指向真正执行断言的测试（门禁 tools/check_route_coverage.py 与
tests/test_09_route_coverage.py 都读这张表）。"""
from tests.helpers import sales_routes  # noqa: F401  (re-export 供工具复用)

COVERED = {
    ("GET", "/api/sales/leads"): "tests/test_03_cross_org.py::test_list_endpoints_are_org_scoped",
    ("GET", "/api/sales/leads/{lead_id}"): "tests/test_01_idor_read.py::test_read_other_consultant_object_404",
    ("PUT", "/api/sales/leads/{lead_id}"): "tests/test_02_idor_write.py::test_write_other_object_rejected",
    ("PATCH", "/api/sales/leads/{lead_id}"): "tests/test_02_idor_write.py::test_write_other_object_rejected",
    ("POST", "/api/sales/leads/{lead_id}/assign"): "tests/test_02_idor_write.py::test_write_other_object_rejected",

    ("GET", "/api/sales/followups"): "tests/test_03_cross_org.py::test_list_endpoints_are_org_scoped",
    ("GET", "/api/sales/followups/{item_id}"): "tests/test_01_idor_read.py::test_read_other_consultant_object_404",
    ("POST", "/api/sales/followups"): "tests/test_02_idor_write.py::test_write_other_object_rejected",
    ("PUT", "/api/sales/followups/{item_id}"): "tests/test_02_idor_write.py::test_write_other_object_rejected",
    ("PATCH", "/api/sales/followups/{item_id}"): "tests/test_02_idor_write.py::test_write_other_object_rejected",

    ("GET", "/api/sales/visits"): "tests/test_03_cross_org.py::test_list_endpoints_are_org_scoped",
    ("GET", "/api/sales/visits/{item_id}"): "tests/test_01_idor_read.py::test_read_other_consultant_object_404",
    ("POST", "/api/sales/visits"): "tests/test_02_idor_write.py::test_write_other_object_rejected",
    ("PUT", "/api/sales/visits/{item_id}"): "tests/test_02_idor_write.py::test_write_other_object_rejected",
    ("PATCH", "/api/sales/visits/{item_id}"): "tests/test_02_idor_write.py::test_write_other_object_rejected",

    ("GET", "/api/sales/quotes"): "tests/test_03_cross_org.py::test_list_endpoints_are_org_scoped",
    ("GET", "/api/sales/quotes/{item_id}"): "tests/test_01_idor_read.py::test_read_other_consultant_object_404",
    ("POST", "/api/sales/quotes"): "tests/test_04_amount_inject.py::test_quote_amounts_come_from_engine",
    ("PUT", "/api/sales/quotes/{item_id}"): "tests/test_04_amount_inject.py::test_quote_amounts_come_from_engine",
    ("PATCH", "/api/sales/quotes/{item_id}"): "tests/test_02_idor_write.py::test_write_other_object_rejected",
    ("POST", "/api/sales/quotes/{item_id}/submit"): "tests/test_05_approval.py::test_happy_path_two_steps",
    ("POST", "/api/sales/quotes/{item_id}/approve"): "tests/test_05_approval.py::test_self_approval_rejected",

    ("GET", "/api/sales/contracts"): "tests/test_03_cross_org.py::test_list_endpoints_are_org_scoped",
    ("GET", "/api/sales/contracts/{item_id}"): "tests/test_01_idor_read.py::test_read_other_consultant_object_404",
    ("PATCH", "/api/sales/contracts/{item_id}"): "tests/test_02_idor_write.py::test_write_other_object_rejected",
    ("POST", "/api/sales/contracts/{item_id}/sign"): "tests/test_02_idor_write.py::test_write_other_object_rejected",

    ("GET", "/api/sales/attachments"): "tests/test_03_cross_org.py::test_list_endpoints_are_org_scoped",
    ("POST", "/api/sales/attachments"): "tests/test_02_idor_write.py::test_write_other_object_rejected",
    ("POST", "/api/sales/attachments/presign"): "tests/test_07_presign.py::test_presigned_link_expires_after_5_minutes",
    ("GET", "/api/sales/attachments/download"): "tests/test_07_presign.py::test_presigned_link_expires_after_5_minutes",
    ("GET", "/api/sales/attachments/{item_id}"): "tests/test_01_idor_read.py::test_read_other_consultant_object_404",

    ("GET", "/api/sales/public-pool"): "tests/test_06_public_pool.py::test_public_pool_has_no_full_phone",
    ("POST", "/api/sales/esign/callback"): "tests/test_08_esign.py::test_forged_signature_rejected",
}

# 写路由（用于金额注入矩阵的参数化基准）
WRITE_METHODS = ("POST", "PUT", "PATCH")
