# -*- coding: utf-8 -*-
"""#2904 归属判定：并发、保护期、四类拒绝与身份不泄露。

断言全部基于真实 SQLite（WAL + 部分唯一索引 + BEGIN IMMEDIATE）与真实多线程并发。
"""
import json
import os
from datetime import timedelta

from app.attribution import AttributionService
from app.db import init_db
from app.normalize import build_keys, normalize_name, phone_hash
from harness import BASE, make_report, race

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------- AC1 并发只有一单成功
def test_01_twenty_rounds_two_threads_only_one_accepted(svc):
    accepted_total = 0
    for round_no in range(20):
        suffix = "%03d" % round_no
        reports = [
            make_report("CH-001", "并发虚构企业%s有限公司" % suffix, "91420100MA4K%s0001" % suffix,
                        "1380013%04d" % round_no),
            make_report("CH-002", "并发虚构企业%s有限公司" % suffix, "91420100MA4K%s0001" % suffix,
                        "1390013%04d" % round_no),
        ]
        results = race(svc, reports)
        statuses = sorted(r["status"] for r in results)
        assert statuses == ["accepted", "rejected_duplicate"], (round_no, results)
        winner = [r for r in results if r["status"] == "accepted"][0]
        assert len(svc.active_keys(winner["report_id"])) == 3
        accepted_total += 1
    assert accepted_total == 20


def test_02_eight_concurrent_submissions_single_winner(svc):
    reports = [make_report("CH-001", "八方并发虚构有限公司", "91420100MA4K8888X1",
                           "1380013%04d" % i) for i in range(8)]
    results = race(svc, reports)
    assert [r["status"] for r in results].count("accepted") == 1
    assert [r["status"] for r in results].count("rejected_duplicate") == 7
    assert not any(r["status"] == "EXCEPTION" for r in results), results


# ---------------------------------------------------------------- AC2 到期释放与再报备
def test_03_expiry_job_releases_keys(svc):
    accepted = svc.decide(make_report(), now=BASE)
    assert accepted["status"] == "accepted"
    assert len(svc.active_keys(accepted["report_id"])) == 3

    early = svc.expire_due(now=BASE + timedelta(days=30))
    assert early["expired"] == 0

    due = svc.expire_due(now=BASE + timedelta(days=91))
    assert due["expired"] == 1
    assert svc.get(accepted["report_id"])["status"] == "expired"
    assert svc.active_keys(accepted["report_id"]) == []


def test_04_new_reporter_accepted_after_expiry(svc):
    first = svc.decide(make_report("CH-001"), now=BASE)
    svc.expire_due(now=BASE + timedelta(days=91))
    second = svc.decide(make_report("CH-002", phone="13900139000"),
                        now=BASE + timedelta(days=92))
    assert second["status"] == "accepted"
    assert second["report_id"] != first["report_id"]
    assert len(svc.active_keys(second["report_id"])) == 3


def test_05_extension_once_and_only_thirty_days(svc):
    accepted = svc.decide(make_report(), now=BASE)
    svc.mark_signing_progress(accepted["report_id"], now=BASE + timedelta(days=5))
    extended = svc.extend(accepted["report_id"], now=BASE + timedelta(days=10))
    assert extended["ok"] is True and extended["extension_days"] == 30
    assert extended["protection_until"] == "2027-03-15T10:00:00Z"   # 2026-11-15 + 90 + 30
    again = svc.extend(accepted["report_id"], now=BASE + timedelta(days=11))
    assert again["ok"] is False and again["reason"] == "EXTENSION_LIMIT"


def test_06_extension_requires_signing_progress_and_live_window(svc):
    accepted = svc.decide(make_report(), now=BASE)
    no_progress = svc.extend(accepted["report_id"], now=BASE + timedelta(days=1))
    assert no_progress["reason"] == "NO_SIGNING_PROGRESS"

    svc.mark_signing_progress(accepted["report_id"], now=BASE)
    overdue = svc.extend(accepted["report_id"], now=BASE + timedelta(days=95))
    assert overdue["reason"] == "ALREADY_EXPIRED"


# ---------------------------------------------------------------- AC3 四类拒绝与 reason code
def test_07_missing_subject_rejected_invalid(svc):
    result = svc.decide(make_report(name="", uscc=None), now=BASE)
    assert result["status"] == "rejected_invalid"
    assert result["reason_code"] == "MISSING_SUBJECT"


def test_08_missing_contact_rejected_invalid(svc):
    result = svc.decide(make_report(phone="12345"), now=BASE)
    assert result["status"] == "rejected_invalid"
    assert result["reason_code"] == "MISSING_CONTACT"


def test_09_self_referral_rejected(svc):
    result = svc.decide(make_report("CH-001", "虚构渠道甲科技有限公司",
                                    "91310000MA1FL00001", "13800138001"), now=BASE)
    assert result["status"] == "rejected_invalid"
    assert result["reason_code"] == "SELF_REFERRAL"


def test_10_existing_member_rejected(svc):
    svc.crm.add_member(uscc="91420100MA4K000001", name="武汉虚构科技有限公司")
    result = svc.decide(make_report(), now=BASE)
    assert result["status"] == "rejected_existing_customer"
    assert result["reason_code"] == "EXISTING_MEMBER"


def test_11_churned_within_twelve_months_rejected(svc):
    svc.crm.add_member(uscc="91420100MA4K000001", name="武汉虚构科技有限公司",
                       churned_at=BASE - timedelta(days=100))
    result = svc.decide(make_report(), now=BASE)
    assert result["status"] == "rejected_existing_customer"
    assert result["reason_code"] == "CHURNED_WITHIN_12M"


def test_12_followed_within_sixty_days_rejected(svc):
    svc.crm.add_follow(uscc="91420100MA4K000001", name="武汉虚构科技有限公司",
                       followed_at=BASE - timedelta(days=10))
    result = svc.decide(make_report(), now=BASE)
    assert result["status"] == "rejected_existing_customer"
    assert result["reason_code"] == "FOLLOWED_WITHIN_60D"


def test_13_duplicate_by_uscc(svc):
    first = svc.decide(make_report("CH-001"), now=BASE)
    assert first["status"] == "accepted"
    dup = svc.decide(make_report("CH-002", "另一家企业名称有限公司",
                                 "91420100MA4K000001", "13900139000"), now=BASE)
    assert dup["status"] == "rejected_duplicate"
    assert dup["reason_code"] == "DUPLICATE_USCC"
    assert dup["matched_key"] == "uscc"


def test_14_duplicate_by_normalized_name(svc):
    svc.decide(make_report("CH-001"), now=BASE)
    dup = svc.decide(make_report("CH-002", "武汉虚构科技（集团）有限公司", None, "13900139000"),
                     now=BASE)
    assert dup["status"] == "rejected_duplicate"
    assert dup["reason_code"] == "DUPLICATE_NAME"
    assert dup["first_reported_at"] == "2026-11-15T10:00:00Z"


def test_15_duplicate_by_phone_hash(svc):
    svc.decide(make_report("CH-001"), now=BASE)
    dup = svc.decide(make_report("CH-002", "完全不同的虚构企业有限公司", None, "138-0013-8000"),
                     now=BASE)
    assert dup["status"] == "rejected_duplicate"
    assert dup["reason_code"] == "DUPLICATE_PHONE"


# ---------------------------------------------------------------- AC4 不泄露首单报备方
def test_16_duplicate_response_hides_first_reporter_identity(svc):
    first = svc.decide(make_report("CH-001"), now=BASE)
    dup = svc.decide(make_report("CH-002", "另一家企业名称有限公司",
                                 "91420100MA4K000001", "13900139000"), now=BASE)
    blob = json.dumps(dup, ensure_ascii=False)
    for secret in ("CH-001", "虚构渠道甲", "13800138000"):
        assert secret not in blob, secret
    assert dup["first_reported_at"] == "2026-11-15T10:00:00Z"
    assert first["report_id"] not in blob


def test_17_duplicate_response_field_whitelist(svc):
    svc.decide(make_report("CH-001"), now=BASE)
    dup = svc.decide(make_report("CH-002", "另一家企业名称有限公司", "91420100MA4K000001", "13900139000"), now=BASE)
    assert set(dup) == {"report_id", "status", "reason_code", "matched_key", "first_reported_at"}


# ---------------------------------------------------------------- 边界
def test_18_inactive_reporter_codes(svc):
    cases = {"CH-003": "REPORTER_SUSPENDED", "CH-004": "REPORTER_TERMINATED",
             "RF-002": "REPORTER_DISABLED"}
    for reporter, code in cases.items():
        result = svc.decide(make_report(reporter, "边界虚构企业%s有限公司" % reporter,
                                        None, "13700137000"), now=BASE)
        assert result["status"] == "rejected_reporter_inactive"
        assert result["reason_code"] == code


def test_19_churn_window_boundary(svc):
    svc.crm.add_member(uscc="91420100MA4K00000A", name="边界甲有限公司",
                       churned_at=BASE - timedelta(days=365))
    inside = svc.decide(make_report("CH-001", "边界甲有限公司", "91420100MA4K00000A",
                                    "13600136000"), now=BASE)
    assert inside["reason_code"] == "CHURNED_WITHIN_12M"

    svc.crm.add_member(uscc="91420100MA4K00000B", name="边界乙有限公司",
                       churned_at=BASE - timedelta(days=366))
    outside = svc.decide(make_report("CH-001", "边界乙有限公司", "91420100MA4K00000B",
                                     "13600136001"), now=BASE)
    assert outside["status"] == "accepted"


def test_20_follow_window_boundary(svc):
    svc.crm.add_follow(uscc="91420100MA4K00000C", name="边界丙有限公司",
                       followed_at=BASE - timedelta(days=60))
    inside = svc.decide(make_report("CH-001", "边界丙有限公司", "91420100MA4K00000C",
                                    "13600136002"), now=BASE)
    assert inside["reason_code"] == "FOLLOWED_WITHIN_60D"

    svc.crm.add_follow(uscc="91420100MA4K00000D", name="边界丁有限公司",
                       followed_at=BASE - timedelta(days=61))
    outside = svc.decide(make_report("CH-001", "边界丁有限公司", "91420100MA4K00000D",
                                     "13600136003"), now=BASE)
    assert outside["status"] == "accepted"


def test_21_rule_version_is_locked_at_accept(svc):
    old = svc.decide(make_report("CH-001"), now=BASE)
    assert old["rule_version"] == "v1"
    assert old["protection_until"] == "2027-02-13T10:00:00Z"      # 90 天

    new = svc.decide(make_report("CH-002", "十二月虚构企业有限公司",
                                 "91420100MA4K000009", "13500135000"),
                     now=BASE + timedelta(days=20))                # 2026-12-05 → v2
    assert new["rule_version"] == "v2"
    assert new["protection_until"] == "2027-02-03T10:00:00Z"      # 60 天

    row = svc.get(old["report_id"])
    assert row["rule_version_id"] == "rv-2026-01", "首单必须锁定 v1"


def test_22_protection_until_is_accepted_plus_rule_days(svc):
    accepted = svc.decide(make_report(), now=BASE)
    row = svc.get(accepted["report_id"])
    assert row["accepted_at"] == "2026-11-15T10:00:00Z"
    assert row["protection_until"] == "2027-02-13T10:00:00Z"
    assert row["extensions"] == 0


def test_23_expiry_job_is_idempotent(svc):
    svc.decide(make_report(), now=BASE)
    first = svc.expire_due(now=BASE + timedelta(days=91))
    second = svc.expire_due(now=BASE + timedelta(days=92))
    assert first["expired"] == 1
    assert second["expired"] == 0 and second["checked"] == 0


def test_24_duplicate_rejection_writes_no_keys(svc):
    svc.decide(make_report("CH-001"), now=BASE)
    dup = svc.decide(make_report("CH-002", "另一家企业名称有限公司", "91420100MA4K000001", "13900139000"), now=BASE)
    assert svc.active_keys(dup["report_id"]) == []
    row = svc.get(dup["report_id"])
    assert row["status"] == "rejected_duplicate" and row["protection_until"] is None


def test_25_name_normalization_rules():
    assert normalize_name("武汉虚构科技（集团）有限公司") == normalize_name("武汉虚构科技有限公司")
    assert normalize_name("  武汉 虚构科技 有限公司 ") == "武汉虚构科技"
    assert normalize_name("ＡＢＣ科技股份有限公司") == "abc科技"
    keys = build_keys("91420100ma4k000001", "武汉虚构科技有限公司", "13800138000", "salt")
    assert [k[0].split(":")[0] for k in keys] == ["uscc", "name", "phone"]
    assert keys[0][0] == "uscc:91420100MA4K000001"
    assert len(phone_hash("13800138000", "salt")) == 32


def test_26_same_uscc_different_names_still_single_winner(svc):
    reports = [make_report("CH-001", "异构名称%d有限公司" % i, "91420100MA4K7777X1",
                           "1370013%04d" % i) for i in range(6)]
    results = race(svc, reports)
    assert [r["status"] for r in results].count("accepted") == 1
    assert [r["status"] for r in results].count("rejected_duplicate") == 5
