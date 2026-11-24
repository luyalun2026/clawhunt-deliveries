"""生成虚构埋点 fixture（无任何真实信息）。

运行：python fixtures/build_fixture.py
输出：fixtures/events.json（40+ 条确定性事件，覆盖三个漏斗与页面 pv/uv）
"""
from __future__ import annotations

import json
import pathlib

OUT = pathlib.Path(__file__).with_name("events.json")
DAY = "2026-12-01"
SITE = "11111111-1111-1111-1111-111111111111"
ORG = "22222222-2222-2222-2222-222222222222"

# 联系人 → 企业（假名）
COMPANY = {f"c{i}": ("compA" if i <= 2 else "compB") for i in range(1, 10)}


def at(hour: int, minute: int = 0) -> str:
    """北京时间 hour:minute → UTC ISO 字符串。"""
    utc_hour = (hour - 8) % 24
    day = DAY if hour >= 8 else "2026-11-30"
    return f"{day}T{utc_hour:02d}:{minute:02d}:00Z"


def ev(event_type: str, contact: str | None, hour: int, minute: int = 0,
       page: str | None = None, event_id: str | None = None,
       anon: str | None = None) -> dict:
    item = {
        "event_type": event_type,
        "occurred_at": at(hour, minute),
        "site_id": SITE,
        "org_id": ORG,
        "contact_id": contact,
        "anon_id": anon,
        "page": page,
        "event_id": event_id,
        "company_pid": COMPANY.get(contact or ""),
    }
    return {k: v for k, v in item.items() if v is not None}


def build() -> list[dict]:
    rows: list[dict] = []

    # --- 页面 PV/UV：u1 访问首页 5 次；u2 匿名 1 次 + 认证后 1 次（同一 anon）；u3 访问「我的」1 次
    for m in (0, 5, 10, 15, 20):
        rows.append(ev("page_view", "c1", 10, m, page="pages/home/index"))
    rows.append(ev("page_view", None, 11, 0, page="pages/home/index", anon="a2"))
    rows.append(ev("page_view", "c2", 11, 30, page="pages/home/index", anon="a2"))
    rows.append(ev("page_view", "c3", 12, 0, page="pages/mine/index"))

    # --- 漏斗 1：资源大厅转化 resource_view 8 人 → connect_request 3 人
    for i in range(1, 9):
        rows.append(ev("resource_view", f"c{i}", 9, i))
    for i in (1, 2, 3):
        rows.append(ev("connect_request", f"c{i}", 10, i))

    # --- 漏斗 2：活动报名到场（E1）event_view 6 → register 4 → checkin 3
    for i in range(1, 7):
        rows.append(ev("event_view", f"c{i}", 13, i, event_id="E1"))
    for i in range(1, 5):
        rows.append(ev("event_register", f"c{i}", 14, i, event_id="E1"))
    for i in range(1, 4):
        rows.append(ev("event_checkin", f"c{i}", 15, i, event_id="E1"))

    # --- 漏斗 3：认证 app_launch 9 → auth_apply 5 → auth_success 2
    for i in range(1, 10):
        rows.append(ev("app_launch", f"c{i}", 8, i))
    for i in range(1, 6):
        rows.append(ev("auth_apply", f"c{i}", 9, 30 + i))
    for i in (1, 2):
        rows.append(ev("auth_success", f"c{i}", 10, 30 + i))

    # --- 纯浏览企业：只有 page_view，不计入月活（落在另一个页面，避免干扰首页口径）
    rows.append(ev("page_view", "c9", 16, 0, page="pages/resource/index"))
    return rows


if __name__ == "__main__":
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT} rows={len(data)}")
