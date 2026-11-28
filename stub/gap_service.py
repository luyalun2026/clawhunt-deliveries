# -*- coding: utf-8 -*-
"""知识缺口服务桩：内存计数 + 可查询记录；真实服务由 KB_GAP_BASE_URL 注入。"""
import itertools
import os
import threading


class GapRecorder:
    def __init__(self, base_url=None):
        self.base_url = base_url or os.environ.get("KB_GAP_BASE_URL", "http://stub.local/api/kb/gaps")
        self.records = []
        self.calls = 0
        self._seq = itertools.count(1)
        self._lock = threading.Lock()

    def record(self, *, question, reason, site_id, category=None):
        req = {"id": next(self._seq), "question": question, "reason": reason,
               "site_id": site_id, "asked_at": "2026-11-22T00:00:00Z"}
        if category:
            req["category"] = category
        with self._lock:
            self.calls += 1
            self.records.append({"method": "POST", "url": self.base_url + "", "body": req})
        return {"ok": True, "id": req["id"]}

    def last(self):
        return self.records[-1]["body"] if self.records else None

    def reset(self):
        self.records = []
        self.calls = 0
