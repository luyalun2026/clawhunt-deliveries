# -*- coding: utf-8 -*-
"""三种绕过手法：参数伪造（A）、间接读取（B）、批量导出（C），各 6 例。"""
import pytest

OWN = "site_a1"
OTHER = "site_b1"


# ---------------- A 组：参数/请求头伪造 ----------------
def test_A1_query_site_id_spoof(svc):
    code, body = svc.request("GET", "/api/member_company", token="staff_site_a1", query={"site_id": OTHER})
    assert code == 200 and body["items"] == []


def test_A2_query_site_id_with_big_page_size(svc):
    code, body = svc.request("GET", "/api/contact", token="staff_site_a1",
                             query={"site_id": OTHER, "page_size": 1000})
    assert code == 200
    assert body["page_size"] <= 200
    assert all(i["site_id"] == OWN for i in body["items"])
    assert body["items"] == []


def test_A3_header_site_id_ignored(svc):
    code, body = svc.request("GET", "/api/event", token="staff_site_a1",
                             query={"site_id": OWN}, headers={"X-Site-Id": OTHER})
    assert code == 200
    assert all(i["site_id"] == OWN for i in body["items"])


def test_A4_page_2_of_foreign_site(svc):
    code, body = svc.request("GET", "/api/opportunity", token="staff_site_a1",
                             query={"site_id": OTHER, "page": 2})
    assert code == 200 and body["items"] == []


def test_A5_export_ids_spoof(svc):
    ids = ",".join(f"{p}-{OTHER}-1" for p in ["mem", "con", "eve", "ven", "sop", "opp", "kb_"])
    code, body = svc.request("GET", "/api/export", token="staff_site_a1",
                             query={"resource": "member_company", "ids": ids})
    assert code == 200 and body["count"] == 0


def test_A6_create_with_spoofed_body_and_header(svc):
    code, body = svc.request("POST", "/api/member_company", token="staff_site_a1",
                             body={"site_id": OTHER, "name": "伪造写入"},
                             headers={"X-Site-Id": OTHER})
    assert code == 403 and body["code"] == "FORBIDDEN"


# ---------------- B 组：经关联对象间接读取 ----------------
def test_B1_contact_to_company_other_site(svc):
    code, body = svc.request("GET", f"/api/contact/con-{OTHER}-1/member_company", token="staff_site_a1")
    assert code == 404


def test_B2_event_to_venue_other_site(svc):
    code, body = svc.request("GET", f"/api/event/eve-{OTHER}-1/venue_booking", token="staff_site_a1")
    assert code == 404


def test_B3_sop_to_kb_other_site(svc):
    code, body = svc.request("GET", f"/api/sop_instance/sop-{OTHER}-1/kb_article", token="staff_site_a1")
    assert code == 404


def test_B4_opportunity_to_company_other_site(svc):
    code, body = svc.request("GET", f"/api/opportunity/opp-{OTHER}-1/member_company", token="staff_site_a1")
    assert code == 404


def test_B5_own_object_linked_to_foreign_object(svc):
    # 本会所对象可见，但它关联的目标在别的会所 —— 必须拒绝，而不是跟着主对象放行
    svc.relations[f"con-{OWN}-2"] = {"member_company_id": f"mem-{OTHER}-1"}
    code, body = svc.request("GET", f"/api/contact/con-{OWN}-2/member_company", token="staff_site_a1")
    assert code == 404


def test_B6_cross_org_relation_with_hq(svc):
    code, body = svc.request("GET", f"/api/event/eve-{OWN}-1/venue_booking", token="staff_site_b1")
    assert code == 404


# ---------------- C 组：批量导出 ----------------
def test_C1_full_export_scoped(svc):
    code, body = svc.request("GET", "/api/export", token="staff_site_a1", query={"resource": "contact"})
    assert code == 200 and body["count"] > 0
    assert all(i["site_id"] == OWN for i in body["items"])


def test_C2_export_filtered_foreign_site(svc):
    code, body = svc.request("GET", "/api/export", token="staff_site_a1",
                             query={"resource": "contact", "site_id": OTHER})
    assert code == 200 and body["count"] == 0


def test_C3_export_ignores_paging_no_default_all(svc):
    code, body = svc.request("GET", "/api/export", token="staff_site_a1",
                             query={"resource": "contact", "page": 9})
    assert code == 200 and body["count"] > 0
    assert all(i["site_id"] == OWN for i in body["items"])


def test_C4_export_mixed_ids(svc):
    ids = f"con-{OWN}-1,con-{OTHER}-1,con-{OTHER}-2"
    code, body = svc.request("GET", "/api/export", token="staff_site_a1",
                             query={"resource": "contact", "ids": ids})
    assert code == 200 and body["count"] == 1
    assert body["items"][0]["id"] == f"con-{OWN}-1"


def test_C5_export_csv_has_no_foreign_rows(svc):
    code, body = svc.request("GET", "/api/export", token="staff_site_a1",
                             query={"resource": "opportunity", "format": "csv"})
    assert code == 200 and body["format"] == "csv"
    assert OTHER not in body["content"]
    assert OWN in body["content"]


def test_C6_export_hq_covers_org_only(svc):
    code, body = svc.request("GET", "/api/export", token="hq_alpha", query={"resource": "kb_article"})
    assert code == 200
    sites = {i["site_id"] for i in body["items"]}
    assert sites == {"site_a1", "site_a2"}
    assert OTHER not in sites


# ---------------- 边界补充 ----------------
def test_D1_soft_deleted_hidden_from_staff(svc):
    code, body = svc.request("GET", f"/api/contact/con-{OWN}-del", token="staff_site_a1")
    assert code == 404


def test_D2_soft_deleted_visible_to_hq_with_flag(svc):
    code, body = svc.request("GET", f"/api/contact/con-{OWN}-del", token="hq_alpha",
                             query={"include_deleted": "1"})
    assert code == 200 and body["item"]["id"] == f"con-{OWN}-del"


def test_D3_pagination_overflow(svc):
    code, body = svc.request("GET", "/api/contact", token="staff_site_a1",
                             query={"page": 99, "page_size": 50})
    assert code == 200 and body["items"] == [] and body["total"] >= 1


def test_D4_invalid_paging_rejected(svc):
    code, body = svc.request("GET", "/api/contact", token="staff_site_a1", query={"page": "abc"})
    assert code == 400 and body["code"] == "BAD_REQUEST"


def test_D5_unauthenticated(svc):
    code, body = svc.request("GET", "/api/contact", token=None)
    assert code == 401


def test_D6_write_allowed_in_own_site(svc):
    code, body = svc.request("POST", "/api/event", token="staff_site_a1",
                             body={"name": "本会所新建", "site_id": OWN})
    assert code == 201 and body["item"]["site_id"] == OWN
