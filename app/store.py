"""调用日志存储：每次调用记录 prompt_version 与模型名，可查询。

生产为 PostgreSQL（表 llm_call_log），此处提供同接口 SQLite/内存实现，
字段对接点在 README 注明。
"""
from __future__ import annotations
import sqlite3
import threading
from typing import List, Optional


class CallLogStore:
    def __init__(self, path: Optional[str] = None):
        self._lock = threading.Lock()
        self._last_id: Optional[int] = None
        if path:
            self.conn = sqlite3.connect(path, check_same_thread=False)
        else:
            self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS llm_call_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                field_group TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                model TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                parse_ok INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )"""
        )
        self.conn.commit()

    def record(self, field_group: str, prompt_version: str, model: str, attempt: int, ok: bool = False) -> int:
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO llm_call_log (field_group, prompt_version, model, attempt, parse_ok) VALUES (?,?,?,?,?)",
                (field_group, prompt_version, model, attempt, 1 if ok else 0),
            )
            self.conn.commit()
            self._last_id = cur.lastrowid
            return self._last_id

    def mark_last_ok(self) -> None:
        if self._last_id is None:
            return
        with self._lock:
            self.conn.execute("UPDATE llm_call_log SET parse_ok=1 WHERE id=?", (self._last_id,))
            self.conn.commit()

    def calls_for_group(self, field_group: str) -> List[dict]:
        rows = self.conn.execute(
            "SELECT id, field_group, prompt_version, model, attempt, parse_ok, created_at "
            "FROM llm_call_log WHERE field_group=? ORDER BY id", (field_group,)
        ).fetchall()
        cols = ["id", "field_group", "prompt_version", "model", "attempt", "parse_ok", "created_at"]
        return [dict(zip(cols, r)) for r in rows]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM llm_call_log").fetchone()[0]

    def close(self) -> None:
        with self._lock:
            self.conn.close()
