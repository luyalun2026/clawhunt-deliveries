# -*- coding: utf-8 -*-
"""并发与夹具辅助。"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

BASE = datetime(2026, 11, 15, 10, 0, 0, tzinfo=timezone.utc)


def make_report(reporter_id="CH-001", name="武汉虚构科技有限公司",
                uscc="91420100MA4K000001", phone="13800138000", **extra):
    payload = {"reporter_type": "channel", "reporter_id": reporter_id,
               "company_name": name, "uscc": uscc, "contact_phone": phone,
               "org_id": "org-demo", "site_id": "site-a"}
    payload.update(extra)
    return payload


def race(service, reports, now=None):
    """Barrier 对齐后同时提交，返回与输入同序的结果。"""
    moment = now or BASE
    barrier = threading.Barrier(len(reports))
    results: list = [None] * len(reports)

    def worker(index: int, payload: dict) -> None:
        barrier.wait()
        try:
            results[index] = service.decide(payload, now=moment)
        except Exception as exc:                       # 异常也记录，便于断言"不应发生"
            results[index] = {"status": "EXCEPTION", "error": "%s: %s" % (type(exc).__name__, exc)}

    threads = [threading.Thread(target=worker, args=(i, r)) for i, r in enumerate(reports)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return results
