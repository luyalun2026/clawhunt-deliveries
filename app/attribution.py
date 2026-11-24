# -*- coding: utf-8 -*-
"""归属判定服务：首次报备为准（查重 → 并发控制 → 保护期 → 到期释放）。

判定顺序与 reason code 严格按工单：
1) 基本校验 → 报备方资格 → 自荐
2) 存量客户（在籍会员 / 12 个月内退会 / 60 天内被跟进）
3) 查重（uscc / 归一化企业名 / 手机号哈希 任一命中 active prospect_keys）
4) 受理：同一事务写全部 keys，部分唯一索引保证并发下仅一单成功
5) 通过后锁定规则版本，protection_until = 受理时间 + protection_days
6) 每日任务把到期未转化置 expired 并释放 keys
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from .crm_stub import CrmStub
from .db import connect
from .normalize import build_keys, is_valid_phone, normalize_name, normalize_phone, normalize_uscc, phone_hash
from .rules import load_by_id, load_effective

ACCEPTED = "accepted"
REJECTED_INVALID = "rejected_invalid"
REJECTED_EXISTING = "rejected_existing_customer"
REJECTED_DUPLICATE = "rejected_duplicate"
REJECTED_REPORTER = "rejected_reporter_inactive"
EXPIRED = "expired"

REPORTER_STATUS_CODE = {
    "suspended": "REPORTER_SUSPENDED",
    "terminated": "REPORTER_TERMINATED",
    "disabled": "REPORTER_DISABLED",
}


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


class AttributionService:
    def __init__(self, db_path: str, crm: CrmStub | None = None,
                 salt: str | None = None, clock=None):
        self.db_path = db_path
        self.crm = crm or CrmStub()
        self.salt = salt
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # ------------------------------------------------------------ 内部
    def _conn(self) -> sqlite3.Connection:
        return connect(self.db_path)

    def _now(self, now: datetime | None) -> datetime:
        return now or self.clock()

    def _row(self, report: dict, now_iso: str) -> dict:
        name = (report.get("company_name") or "").strip()
        uscc = normalize_uscc(report.get("uscc"))
        phone = normalize_phone(report.get("contact_phone"))
        return {
            "id": "R-" + uuid.uuid4().hex[:12],
            "org_id": report.get("org_id") or "org-demo",
            "site_id": report.get("site_id"),
            "reporter_type": report.get("reporter_type") or "channel",
            "reporter_id": report["reporter_id"],
            "company_name": name,
            "company_name_norm": normalize_name(name),
            "uscc": uscc,
            "contact_phone": phone,
            "phone_hash": phone_hash(phone, self.salt),
            "created_at": now_iso,
            "created_by": report.get("reporter_id"),
            "updated_at": now_iso,
        }

    def _insert_rejection(self, base: dict, status: str, reason: str) -> str:
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO reports(id, org_id, site_id, reporter_type, reporter_id, company_name,"
                " company_name_norm, uscc, contact_phone, phone_hash, status, reason_code,"
                " created_at, created_by, updated_at)"
                " VALUES(:id,:org_id,:site_id,:reporter_type,:reporter_id,:company_name,"
                ":company_name_norm,:uscc,:contact_phone,:phone_hash,:status,:reason,"
                ":created_at,:created_by,:updated_at)",
                {**base, "status": status, "reason": reason})
            conn.execute("COMMIT")
            return base["id"]
        finally:
            conn.close()

    @staticmethod
    def _first_reported_at(conn: sqlite3.Connection, key: str) -> str | None:
        row = conn.execute("SELECT MIN(created_at) AS t FROM prospect_keys WHERE key=?", (key,)).fetchone()
        return row["t"] if row and row["t"] else None

    def _duplicate(self, conn: sqlite3.Connection, key: str, key_type: str,
                   base: dict, now_iso: str) -> dict:
        report_id = self._insert_rejection(base, REJECTED_DUPLICATE, "DUPLICATE_" + key_type.upper())
        return {
            "report_id": report_id,
            "status": REJECTED_DUPLICATE,
            "reason_code": "DUPLICATE_" + key_type.upper(),
            "matched_key": key_type,
            "first_reported_at": self._first_reported_at(conn, key),
        }

    def _accept(self, keys: list[tuple[str, str]], base: dict, now: datetime) -> dict:
        now_iso = iso(now)
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            for key, key_type in keys:
                hit = conn.execute(
                    "SELECT key FROM prospect_keys WHERE key=? AND is_active=1", (key,)).fetchone()
                if hit is not None:
                    conn.execute("ROLLBACK")
                    return self._duplicate(conn, key, key_type, base, now_iso)
            rule = load_effective(conn, now_iso)
            protection_until = iso(now + timedelta(days=int(rule["protection_days"])))
            conn.execute(
                "INSERT INTO reports(id, org_id, site_id, reporter_type, reporter_id, company_name,"
                " company_name_norm, uscc, contact_phone, phone_hash, status, reason_code,"
                " rule_version_id, accepted_at, protection_until, extensions, signing_progress,"
                " created_at, created_by, updated_at)"
                " VALUES(:id,:org_id,:site_id,:reporter_type,:reporter_id,:company_name,"
                ":company_name_norm,:uscc,:contact_phone,:phone_hash,'accepted',NULL,"
                ":rule_id,:now_iso,:until,0,0,:created_at,:created_by,:now_iso)",
                {**base, "rule_id": rule["id"], "now_iso": now_iso, "until": protection_until})
            for key, _ in keys:
                conn.execute(
                    "INSERT INTO prospect_keys(key, report_id, is_active, created_at) VALUES(?,?,1,?)",
                    (key, base["id"], now_iso))
            conn.execute("COMMIT")
            return {
                "report_id": base["id"],
                "status": ACCEPTED,
                "reason_code": None,
                "rule_version": rule["version"],
                "accepted_at": now_iso,
                "protection_until": protection_until,
            }
        except sqlite3.IntegrityError:
            # 并发下的败者：唯一索引拒绝写入 → 转 rejected_duplicate
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            for key, key_type in keys:
                hit = conn.execute(
                    "SELECT key FROM prospect_keys WHERE key=? AND is_active=1", (key,)).fetchone()
                if hit is not None:
                    return self._duplicate(conn, key, key_type, base, now_iso)
            return self._duplicate(conn, keys[0][0], keys[0][1], base, now_iso)
        finally:
            conn.close()

    # ------------------------------------------------------------ 对外
    def decide(self, report: dict, now: datetime | None = None) -> dict:
        moment = self._now(now)
        now_iso = iso(moment)
        base = self._row(report, now_iso)
        conn = self._conn()
        try:
            reporter = conn.execute(
                "SELECT * FROM reporters WHERE id=? AND deleted_at IS NULL",
                (report["reporter_id"],)).fetchone()
            if reporter is None:
                return {"report_id": self._insert_rejection(base, REJECTED_REPORTER, "REPORTER_NOT_FOUND"),
                        "status": REJECTED_REPORTER, "reason_code": "REPORTER_NOT_FOUND"}

            if not base["uscc"] and not base["company_name"]:
                return {"report_id": self._insert_rejection(base, REJECTED_INVALID, "MISSING_SUBJECT"),
                        "status": REJECTED_INVALID, "reason_code": "MISSING_SUBJECT"}
            if not is_valid_phone(base["contact_phone"]):
                return {"report_id": self._insert_rejection(base, REJECTED_INVALID, "MISSING_CONTACT"),
                        "status": REJECTED_INVALID, "reason_code": "MISSING_CONTACT"}

            if reporter["status"] != "active":
                code = REPORTER_STATUS_CODE.get(reporter["status"], "REPORTER_DISABLED")
                return {"report_id": self._insert_rejection(base, REJECTED_REPORTER, code),
                        "status": REJECTED_REPORTER, "reason_code": code}

            if base["uscc"] and reporter["uscc"] and base["uscc"] == reporter["uscc"].upper():
                return {"report_id": self._insert_rejection(base, REJECTED_INVALID, "SELF_REFERRAL"),
                        "status": REJECTED_INVALID, "reason_code": "SELF_REFERRAL"}

            existing = self.crm.check(base["uscc"], base["company_name"], moment)
            if existing:
                return {"report_id": self._insert_rejection(base, REJECTED_EXISTING, existing),
                        "status": REJECTED_EXISTING, "reason_code": existing}

            keys = build_keys(base["uscc"], base["company_name"], base["contact_phone"], self.salt)
            for key, key_type in keys:
                hit = conn.execute(
                    "SELECT key FROM prospect_keys WHERE key=? AND is_active=1", (key,)).fetchone()
                if hit is not None:
                    return self._duplicate(conn, key, key_type, base, now_iso)
        finally:
            conn.close()

        return self._accept(keys, base, moment)

    def mark_signing_progress(self, report_id: str, now: datetime | None = None) -> dict:
        conn = self._conn()
        try:
            cur = conn.execute(
                "UPDATE reports SET signing_progress=1, updated_at=? WHERE id=? AND status='accepted'",
                (iso(self._now(now)), report_id))
            return {"updated": cur.rowcount}
        finally:
            conn.close()

    def extend(self, report_id: str, now: datetime | None = None) -> dict:
        moment = self._now(now)
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
            if row is None:
                return {"ok": False, "reason": "NOT_FOUND"}
            if row["status"] != ACCEPTED:
                return {"ok": False, "reason": "NOT_ACTIVE", "status": row["status"]}
            if not row["signing_progress"]:
                return {"ok": False, "reason": "NO_SIGNING_PROGRESS"}
            rule = load_by_id(conn, row["rule_version_id"])
            if row["extensions"] >= int(rule["max_extensions"]):
                return {"ok": False, "reason": "EXTENSION_LIMIT"}
            if parse_iso(row["protection_until"]) <= moment:
                return {"ok": False, "reason": "ALREADY_EXPIRED"}
            new_until = parse_iso(row["protection_until"]) + timedelta(days=int(rule["extension_days"]))
            conn.execute(
                "UPDATE reports SET protection_until=?, extensions=extensions+1, updated_at=? WHERE id=?",
                (iso(new_until), iso(moment), report_id))
            return {"ok": True, "protection_until": iso(new_until),
                    "extensions": int(row["extensions"]) + 1,
                    "extension_days": int(rule["extension_days"])}
        finally:
            conn.close()

    def expire_due(self, now: datetime | None = None) -> dict:
        """每日任务：到期未转化 → expired，并释放 prospect_keys。可重复执行（幂等）。"""
        moment = self._now(now)
        now_iso = iso(moment)
        conn = self._conn()
        expired = 0
        try:
            rows = conn.execute(
                "SELECT id FROM reports WHERE status='accepted' AND signing_progress=0"
                " AND protection_until <= ?", (now_iso,)).fetchall()
            for row in rows:
                conn.execute("BEGIN IMMEDIATE")
                cur = conn.execute(
                    "UPDATE reports SET status='expired', updated_at=?"
                    " WHERE id=? AND status='accepted' AND signing_progress=0", (now_iso, row["id"]))
                if cur.rowcount:
                    conn.execute(
                        "UPDATE prospect_keys SET is_active=0, released_at=?"
                        " WHERE report_id=? AND is_active=1", (now_iso, row["id"]))
                    expired += 1
                conn.execute("COMMIT")
            return {"checked": len(rows), "expired": expired, "at": now_iso}
        finally:
            conn.close()

    def get(self, report_id: str) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def active_keys(self, report_id: str) -> list[str]:
        conn = self._conn()
        try:
            return [r["key"] for r in conn.execute(
                "SELECT key FROM prospect_keys WHERE report_id=? AND is_active=1 ORDER BY id",
                (report_id,))]
        finally:
            conn.close()
