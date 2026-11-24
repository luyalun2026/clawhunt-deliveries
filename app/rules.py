# -*- coding: utf-8 -*-
"""规则版本：按生效时间取当时版本，受理时锁定。"""
from __future__ import annotations

import sqlite3


def load_effective(conn: sqlite3.Connection, now_iso: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM rule_versions WHERE effective_from <= ? ORDER BY effective_from DESC LIMIT 1",
        (now_iso,)).fetchone()
    if row is None:
        raise RuntimeError("no effective rule version at " + now_iso)
    return row


def load_by_id(conn: sqlite3.Connection, rule_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM rule_versions WHERE id=?", (rule_id,)).fetchone()
    if row is None:
        raise RuntimeError("rule version not found: " + rule_id)
    return row
