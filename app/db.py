# -*- coding: utf-8 -*-
"""存储层：SQLite 离线可跑，DDL 与 PostgreSQL 16 兼容（含部分唯一索引）。

生产部署把 connect() 换成 psycopg 连接即可，SQL 与索引语义不变：
    CREATE UNIQUE INDEX ux_prospect_keys_active ON prospect_keys(key) WHERE is_active = 1;
"""
from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS rule_versions (
  id              TEXT PRIMARY KEY,
  version         TEXT NOT NULL,
  protection_days INTEGER NOT NULL,
  extension_days  INTEGER NOT NULL,
  max_extensions  INTEGER NOT NULL,
  effective_from  TEXT NOT NULL,
  created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reporters (
  id         TEXT PRIMARY KEY,
  kind       TEXT NOT NULL,              -- channel | referrer
  name       TEXT NOT NULL,
  uscc       TEXT,
  status     TEXT NOT NULL,              -- active | suspended | terminated | disabled
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS reports (
  id               TEXT PRIMARY KEY,
  org_id           TEXT NOT NULL,
  site_id          TEXT,
  reporter_type    TEXT NOT NULL,
  reporter_id      TEXT NOT NULL,
  company_name     TEXT NOT NULL,
  company_name_norm TEXT NOT NULL,
  uscc             TEXT,
  contact_phone    TEXT NOT NULL,
  phone_hash       TEXT NOT NULL,
  status           TEXT NOT NULL,
  reason_code      TEXT,
  rule_version_id  TEXT,
  accepted_at      TEXT,
  protection_until TEXT,
  extensions       INTEGER NOT NULL DEFAULT 0,
  signing_progress INTEGER NOT NULL DEFAULT 0,
  created_at       TEXT NOT NULL,
  created_by       TEXT,
  updated_at       TEXT NOT NULL,
  deleted_at       TEXT
);

CREATE TABLE IF NOT EXISTS prospect_keys (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  key         TEXT NOT NULL,
  report_id   TEXT NOT NULL,
  is_active   INTEGER NOT NULL DEFAULT 1,
  created_at  TEXT NOT NULL,
  released_at TEXT
);

-- 并发下的唯一性最终由该部分唯一索引保证：同一 key 同时只能有一条 active
CREATE UNIQUE INDEX IF NOT EXISTS ux_prospect_keys_active
  ON prospect_keys(key) WHERE is_active = 1;

CREATE INDEX IF NOT EXISTS ix_reports_reporter ON reports(reporter_id, status);
CREATE INDEX IF NOT EXISTS ix_reports_status ON reports(status, protection_until);
"""

SEED_RULES = [
    ("rv-2026-01", "v1", 90, 30, 1, "2026-01-01T00:00:00Z"),
    ("rv-2026-12", "v2", 60, 15, 1, "2026-12-01T00:00:00Z"),
]

SEED_REPORTERS = [
    ("CH-001", "channel", "虚构渠道甲", "91310000MA1FL00001", "active"),
    ("CH-002", "channel", "虚构渠道乙", "91310000MA1FL00002", "active"),
    ("CH-003", "channel", "虚构渠道丙（暂停）", "91310000MA1FL00003", "suspended"),
    ("CH-004", "channel", "虚构渠道丁（终止）", "91310000MA1FL00004", "terminated"),
    ("RF-001", "referrer", "虚构转介绍人甲", None, "active"),
    ("RF-002", "referrer", "虚构转介绍人乙（停用）", None, "disabled"),
    ("RF-003", "referrer", "虚构转介绍人丙", None, "active"),
]


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=15, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def init_db(path: str) -> None:
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.execute("BEGIN IMMEDIATE")
        for rid, version, days, ext, max_ext, start in SEED_RULES:
            conn.execute(
                "INSERT OR IGNORE INTO rule_versions"
                "(id, version, protection_days, extension_days, max_extensions, effective_from, created_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (rid, version, days, ext, max_ext, start, start))
        for rid, kind, name, uscc, status in SEED_REPORTERS:
            conn.execute(
                "INSERT OR IGNORE INTO reporters(id, kind, name, uscc, status, created_at, updated_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (rid, kind, name, uscc, status, "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"))
        conn.execute("COMMIT")
    finally:
        conn.close()
