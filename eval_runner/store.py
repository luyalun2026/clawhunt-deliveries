# -*- coding: utf-8 -*-
"""结果落库：eval_run / eval_result 两张表。

生产环境为 PostgreSQL 16（DDL 见 schema.sql，含 org_id / site_id / 软删除字段与 UUID 主键）；
本地与 CI 用同构的 SQLite 实现，字段名与语义完全一致，便于直接迁移。
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS eval_run (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    suite_key TEXT NOT NULL,
    target TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    options_json TEXT NOT NULL DEFAULT '{}',
    total INTEGER NOT NULL DEFAULT 0,
    pass_rate REAL,
    exit_code INTEGER,
    duration_ms INTEGER,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE TABLE IF NOT EXISTS eval_result (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    status TEXT NOT NULL,
    latency_ms INTEGER NOT NULL,
    attempts INTEGER NOT NULL,
    tokens_in INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    output_json TEXT,
    created_at TEXT NOT NULL,
    created_by TEXT,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    UNIQUE (run_id, case_id)
);
CREATE INDEX IF NOT EXISTS idx_eval_result_run ON eval_result(run_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Store:
    def __init__(self, path: str = "db/eval.sqlite3") -> None:
        parent = os.path.dirname(os.path.abspath(path))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SQLITE_DDL)
        self.conn.commit()

    # ---- run ----
    def create_run(self, run_id: str, org_id: str, site_id: str, suite_key: str,
                   target: str, options: dict, created_by: str) -> None:
        ts = _now()
        self.conn.execute(
            "INSERT INTO eval_run (id, org_id, site_id, suite_key, target, status, options_json,"
            " created_by, created_at, updated_at) VALUES (?,?,?,?,?,'running',?,?,?,?)",
            (run_id, org_id, site_id, suite_key, target,
             json.dumps({k: v for k, v in options.items() if k != "resume_run_id"},
                        ensure_ascii=False),
             created_by, ts, ts),
        )
        self.conn.commit()

    def mark_run_status(self, run_id: str, status: str) -> None:
        self.conn.execute("UPDATE eval_run SET status=?, updated_at=? WHERE id=?",
                          (status, _now(), run_id))
        self.conn.commit()

    def finish_run(self, run_id: str, exit_code: int, pass_rate: float,
                   total: int, duration_ms: int) -> None:
        self.conn.execute(
            "UPDATE eval_run SET status='finished', exit_code=?, pass_rate=?, total=?,"
            " duration_ms=?, updated_at=? WHERE id=?",
            (exit_code, pass_rate, total, duration_ms, _now(), run_id),
        )
        self.conn.commit()

    # ---- result ----
    def add_result(self, run_id: str, res, org_id: str, site_id: str, created_by: str = "eval-runner") -> None:
        ts = _now()
        self.conn.execute(
            "INSERT OR REPLACE INTO eval_result (id, org_id, site_id, run_id, case_id, status,"
            " latency_ms, attempts, tokens_in, tokens_out, error, output_json, created_at,"
            " created_by, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), org_id, site_id, run_id, res.case_id, res.status,
             res.latency_ms, res.attempts, res.tokens_in, res.tokens_out, res.error,
             json.dumps(res.output, ensure_ascii=False) if res.output else None,
             ts, created_by, ts),
        )
        self.conn.commit()

    def completed_case_ids(self, run_id: str) -> set[str]:
        rows = self.conn.execute(
            "SELECT case_id FROM eval_result WHERE run_id=? AND deleted_at IS NULL", (run_id,)
        ).fetchall()
        return {r["case_id"] for r in rows}

    def results_for_run(self, run_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT case_id, status, latency_ms, attempts, tokens_in, tokens_out, error"
            " FROM eval_result WHERE run_id=? AND deleted_at IS NULL ORDER BY created_at",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:  # noqa: BLE001
            pass
