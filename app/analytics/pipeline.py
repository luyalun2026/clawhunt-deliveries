"""日汇总任务：page_daily_stats / funnel_daily_stats / monthly_active_companies。

口径（README 同步说明）：
- 统计日按事件 occurred_at（UTC）转 Asia/Shanghai 后的日期切分。
- uv = COUNT(DISTINCT COALESCE(contact_id, anon_id))；同一 anon_id 当天先匿名后
  认证的场景，先按 anon_id 去重、再按 contact_id 去重，最后取两者并集，避免同一
  人被记两次。
- 漏斗不要求严格时序（可开启 STRICT_FUNNEL=1 改为严格时序）。
- 某日无事件时不写 0 行；重跑先 DELETE 当日再 INSERT，全程单事务。
"""
from __future__ import annotations

import datetime as dt
import os
import uuid
from collections import defaultdict
from typing import Iterable

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from .models import FunnelDailyStat, MonthlyActiveCompany, PageDailyStat

SHANGHAI = dt.timezone(dt.timedelta(hours=8))
STRICT_FUNNEL = os.environ.get("STRICT_FUNNEL") == "1"

# 漏斗定义：code -> [(step_key, step_index, event_type)]
FUNNEL_DEFS: dict[str, list[tuple[str, int, str]]] = {
    "resource_connect": [
        ("resource_view", 1, "resource_view"),
        ("connect_request", 2, "connect_request"),
    ],
    "event_attendance": [
        ("event_view", 1, "event_view"),
        ("event_register", 2, "event_register"),
        ("event_checkin", 3, "event_checkin"),
    ],
    "auth": [
        ("app_launch", 1, "app_launch"),
        ("auth_apply", 2, "auth_apply"),
        ("auth_success", 3, "auth_success"),
    ],
}

# 有效互动的定义：认证、发布、报名、签到、提问；纯浏览不计入月活
EFFECTIVE_EVENT_TYPES = {
    "auth_apply", "auth_success", "resource_publish", "resource_response",
    "event_register", "event_checkin", "butler_question", "connect_request",
}


def local_date(occurred_at: dt.datetime) -> dt.date:
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=dt.timezone.utc)
    return occurred_at.astimezone(SHANGHAI).date()


def _user_key(ev: dict) -> str:
    return str(ev.get("contact_id") or ev.get("anon_id") or ev.get("user_id"))


def _distinct_users(events: Iterable[dict]) -> int:
    """anon/contact 两段并集去重。

    同一 anon_id 的当天事件若部分带 contact_id，说明该人当天完成了认证：按 anon_id
    聚合后取其一，故先按 anon 归并、再按 contact 归并，最后取并集大小。
    """
    by_anon: dict[str, set[str]] = defaultdict(set)
    by_contact: dict[str, set[str]] = defaultdict(set)
    loose: set[str] = set()
    for ev in events:
        anon, contact = ev.get("anon_id"), ev.get("contact_id")
        if anon and contact:
            by_anon[str(anon)].add(str(contact))
        elif contact:
            by_contact[str(contact)].add(str(contact))
        elif anon:
            by_anon[str(anon)].add(str(anon))
        else:
            loose.add(str(ev.get("user_id")))
    merged: set[str] = set(loose)
    for keys in by_anon.values():
        merged.add(sorted(keys)[0])
    for keys in by_contact.values():
        merged.add(sorted(keys)[0])
    return len(merged)


def aggregate(events: list[dict], stat_date: dt.date,
              site_id: uuid.UUID, org_id: uuid.UUID) -> tuple[list[dict], list[dict]]:
    """纯函数：输入当日事件，输出 (page_rows, funnel_rows)，便于单测。"""
    day_events = [e for e in events if local_date(_parse(e["occurred_at"])) == stat_date]

    pages: dict[str, list[dict]] = defaultdict(list)
    for ev in day_events:
        if ev["event_type"] == "page_view":
            pages[ev["page"]].append(ev)
    page_rows = [
        {
            "id": uuid.uuid4(), "org_id": org_id, "site_id": site_id,
            "stat_date": stat_date, "page": page, "pv": len(evs),
            "uv": _distinct_users(evs),
        }
        for page, evs in sorted(pages.items())
    ]

    funnel_rows: list[dict] = []
    for code, steps in FUNNEL_DEFS.items():
        for step_key, step_index, event_type in steps:
            # 活动漏斗按 event_id 拆分
            scopes: dict[str, list[dict]] = defaultdict(list)
            for ev in day_events:
                if ev["event_type"] != event_type:
                    continue
                if code == "event_attendance":
                    scopes[str(ev.get("event_id") or "-")].append(ev)
                else:
                    scopes["-"].append(ev)
            for scope_key, evs in sorted(scopes.items()):
                funnel_rows.append({
                    "id": uuid.uuid4(), "org_id": org_id, "site_id": site_id,
                    "stat_date": stat_date, "funnel_code": code,
                    "scope_key": scope_key, "step_key": step_key,
                    "step_index": step_index, "user_count": _distinct_users(evs),
                })

    if STRICT_FUNNEL:
        funnel_rows = _apply_strict_order(funnel_rows, day_events)
    return page_rows, funnel_rows


def _apply_strict_order(rows: list[dict], day_events: list[dict]) -> list[dict]:
    """严格时序：第 n 步只统计「此前各步都出现过」的用户（集合交集）。"""
    by_key: dict[tuple[str, str], set[str]] = defaultdict(set)
    for ev in day_events:
        scope = str(ev.get("event_id") or "-") if ev["event_type"].startswith("event_") else "-"
        by_key[(ev["event_type"], scope)].add(_user_key(ev))
    out = []
    for row in rows:
        steps = FUNNEL_DEFS[row["funnel_code"]]
        idx = row["step_index"]
        users: set[str] | None = None
        for step_key, step_index, event_type in steps[:idx]:
            bucket = by_key[(event_type, row["scope_key"])]
            users = set(bucket) if users is None else users & bucket
        out.append(dict(row, user_count=len(users or set())))
    return out


def _parse(value) -> dt.datetime:
    if isinstance(value, dt.datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    return dt.datetime.fromisoformat(text)


def run_day(session: Session, events: list[dict], stat_date: dt.date,
            site_id: uuid.UUID, org_id: uuid.UUID) -> dict[str, int]:
    """重算某日：先删后插，单事务，幂等。"""
    page_rows, funnel_rows = aggregate(events, stat_date, site_id, org_id)

    session.execute(delete(PageDailyStat).where(
        PageDailyStat.stat_date == stat_date, PageDailyStat.site_id == site_id))
    session.execute(delete(FunnelDailyStat).where(
        FunnelDailyStat.stat_date == stat_date, FunnelDailyStat.site_id == site_id))
    if page_rows:
        session.execute(insert(PageDailyStat), page_rows)
    if funnel_rows:
        session.execute(insert(FunnelDailyStat), funnel_rows)

    # 月活：当月有有效事件的已认证企业
    month = stat_date.strftime("%Y-%m")
    actives: set[str] = set()
    for ev in events:
        if local_date(_parse(ev["occurred_at"])).strftime("%Y-%m") != month:
            continue
        if ev["event_type"] not in EFFECTIVE_EVENT_TYPES:
            continue
        company = ev.get("company_pid") or ev.get("company_id")
        if company:
            actives.add(str(company))
    session.execute(delete(MonthlyActiveCompany).where(
        MonthlyActiveCompany.month == month, MonthlyActiveCompany.site_id == site_id))
    if actives:
        session.execute(insert(MonthlyActiveCompany), [
            {"id": uuid.uuid4(), "org_id": org_id, "site_id": site_id,
             "month": month, "company_pid": pid}
            for pid in sorted(actives)
        ])
    return {"page_rows": len(page_rows), "funnel_rows": len(funnel_rows),
            "active_companies": len(actives)}


def read_page_stats(session: Session) -> list[tuple]:
    rows = session.execute(
        select(PageDailyStat.stat_date, PageDailyStat.page, PageDailyStat.pv, PageDailyStat.uv)
        .order_by(PageDailyStat.page)
    ).all()
    return [tuple(r) for r in rows]


def read_funnel_stats(session: Session) -> list[tuple]:
    rows = session.execute(
        select(FunnelDailyStat.funnel_code, FunnelDailyStat.scope_key, FunnelDailyStat.step_key,
               FunnelDailyStat.user_count)
        .order_by(FunnelDailyStat.funnel_code, FunnelDailyStat.scope_key, FunnelDailyStat.step_index)
    ).all()
    return [tuple(r) for r in rows]
