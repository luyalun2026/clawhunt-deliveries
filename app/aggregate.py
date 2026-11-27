# -*- coding: utf-8 -*-
"""S6-POD-040 日汇总任务核心实现。

python -m app.aggregate --from 2026-11-01 --to 2026-11-07 [--db sqlite:///...]
默认无参数 = 汇总昨天（Asia/Shanghai）。

口径（与 docs/口径文档.md 同义）：
  views              episode_view 事件数（不去重）
  plays              play_start 按 session_id 去重
  unique_listeners   user_id 优先、NULL 用 anon_id，去重
  listen_seconds     played_delta_sec 求和（事件按其 stat_date 归属，跨午夜随事件时间戳）
  completes          有 complete 事件的去重听众数
  completion_rate    completes / unique_listeners（分母 0 → NULL）
  avg_listen_ratio   listen_seconds / (unique_listeners × 节目时长)（时长缺失 → NULL）
  reach_N            听众级最大进度 ≥ N% 的去重听众数（同一听众跨事件取最大进度后判档）
  source_breakdown   {"<source>": {"plays": n, "listeners": m}} 按 plays 降序；未知 source 原样保留
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import defaultdict
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import ColumnDailyStats, Episode, EpisodeDailyStats, ListeningEvent

TZ = ZoneInfo("Asia/Shanghai")
ALL_KEY = "__ALL__"
REACH_LEVELS = (10, 20, 30, 40, 50, 60, 70, 80, 90, 100)


def stat_date_of(ts: dt.datetime) -> dt.date:
    """事件时间 → Asia/Shanghai 本地日期（跨午夜归属按此）。"""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    return ts.astimezone(TZ).date()


def _listener_key(user_id, anon_id):
    return ("u", user_id) if user_id else ("a", anon_id)


def aggregate_day(session: Session, day: dt.date, org_id: str = "org_demo") -> dict:
    """单日汇总：先删后插（单事务），返回 {'episode': n, 'column': n, 'all': 1}。"""
    d_start = dt.datetime.combine(day, dt.time.min, tzinfo=TZ)
    d_end = d_start + dt.timedelta(days=1)

    events = session.execute(
        select(ListeningEvent, Episode)
        .join(Episode, ListeningEvent.episode_id == Episode.id)
        .where(ListeningEvent.deleted_at.is_(None),
               ListeningEvent.ts >= d_start, ListeningEvent.ts < d_end)
    ).all()

    per_episode = defaultdict(lambda: {
        "views": 0, "play_sessions": set(), "listeners": set(),
        "listen_seconds": 0, "complete_listeners": set(),
        "max_progress": defaultdict(float), "sources": defaultdict(lambda: {"plays": set(), "listeners": set()}),
    })
    episode_meta = {}

    for ev, ep in events:
        ep_id = ev.episode_id
        bucket = per_episode[ep_id]
        episode_meta[ep_id] = {"column_id": ep.column_id, "duration_sec": ep.duration_sec}
        key = _listener_key(ev.user_id, ev.anon_id)
        if ev.event_type == "episode_view":
            bucket["views"] += 1
        elif ev.event_type == "play_start":
            if ev.session_id:
                bucket["play_sessions"].add(ev.session_id)
            bucket["listeners"].add(key)
            bucket["sources"][ev.source]["plays"].add(ev.session_id or key)
            bucket["sources"][ev.source]["listeners"].add(key)
        elif ev.event_type == "progress":
            bucket["listeners"].add(key)
            if ev.progress_pct is not None:
                prev = bucket["max_progress"][key]
                bucket["max_progress"][key] = max(prev, float(ev.progress_pct))
            bucket["sources"][ev.source]["listeners"].add(key)
        elif ev.event_type == "complete":
            bucket["listeners"].add(key)
            bucket["complete_listeners"].add(key)
            bucket["sources"][ev.source]["listeners"].add(key)
        if ev.played_delta_sec:
            bucket["listen_seconds"] += int(ev.played_delta_sec)

    session.execute(delete(EpisodeDailyStats).where(
        EpisodeDailyStats.org_id == org_id, EpisodeDailyStats.stat_date == day))
    session.execute(delete(ColumnDailyStats).where(
        ColumnDailyStats.org_id == org_id, ColumnDailyStats.stat_date == day))

    counts = {"episode": 0, "column": 0, "all": 0}
    all_row = _new_row(EpisodeDailyStats, org_id, ALL_KEY, day)

    for ep_id, b in sorted(per_episode.items()):
        meta = episode_meta[ep_id]
        row = _fill_row(_new_row(EpisodeDailyStats, org_id, ep_id, day), b,
                        meta["duration_sec"])
        session.add(row)
        counts["episode"] += 1
        _merge_into_all(all_row, b)

    for level in REACH_LEVELS:
        # 全站 reach：听众级跨节目合并会重复计人，全站档位按「该日该听众最大进度」独立统计
        setattr(all_row, f"reach_{level}", _count_reach_global(per_episode, level))
    session.add(all_row)
    counts["all"] = 1

    per_column = defaultdict(list)
    for ep_id, b in per_episode.items():
        per_column[episode_meta[ep_id]["column_id"]].append((ep_id, b))
    for col_id, members in sorted(per_column.items()):
        merged = _merge_buckets(members)
        col_row = _fill_row(_new_row(ColumnDailyStats, org_id, col_id, day), merged,
                            None)
        session.add(col_row)
        counts["column"] += 1

    return counts


def _merge_buckets(members):
    m = {"views": 0, "play_sessions": set(), "listeners": set(), "listen_seconds": 0,
         "complete_listeners": set(),
         "sources": defaultdict(lambda: {"plays": set(), "listeners": set()})}
    for _, b in members:
        m["views"] += b["views"]
        m["play_sessions"] |= b["play_sessions"]
        m["listeners"] |= b["listeners"]
        m["listen_seconds"] += b["listen_seconds"]
        m["complete_listeners"] |= b["complete_listeners"]
        for s, v in b["sources"].items():
            m["sources"][s]["plays"] |= v["plays"]
            m["sources"][s]["listeners"] |= v["listeners"]
    return m


def _new_row(model, org_id, key, day):
    if model is EpisodeDailyStats:
        return model(org_id=org_id, stat_date=day, episode_id=key)
    return model(org_id=org_id, stat_date=day, column_id=key)


def _fill_row(row, b, duration_sec):
    row.views = b["views"]
    row.plays = len(b["play_sessions"])
    row.unique_listeners = len(b["listeners"])
    row.listen_seconds = b["listen_seconds"]
    row.completes = len(b["complete_listeners"])
    row.completion_rate = (row.completes / row.unique_listeners
                           if row.unique_listeners else None)
    if duration_sec and row.unique_listeners:
        row.avg_listen_ratio = row.listen_seconds / (row.unique_listeners * duration_sec)
    else:
        row.avg_listen_ratio = None
    for level in REACH_LEVELS:
        prog = b.get("max_progress")
        n = sum(1 for v in prog.values() if v + 1e-9 >= level) if prog else 0
        setattr(row, f"reach_{level}", n)
    row.source_breakdown = {
        s: {"plays": len(v["plays"]), "listeners": len(v["listeners"])}
        for s, v in sorted(b["sources"].items(),
                           key=lambda kv: -len(kv[1]["plays"]))
    }
    return row


def _merge_into_all(all_row, b):
    all_row.views = (all_row.views or 0) + b["views"]
    all_row.listen_seconds = (all_row.listen_seconds or 0) + b["listen_seconds"]
    all_row.completes = (all_row.completes or 0) + len(b["complete_listeners"])
    for s, v in b["sources"].items():
        cur = (all_row.source_breakdown or {}).get(s, {"plays": 0, "listeners": 0})
        # 全站 plays/listeners 在 finalize 阶段统一去重重算，这里先累加计数
        cur["plays"] += len(v["plays"])
        cur["listeners"] += len(v["listeners"])
        all_row.source_breakdown = {**(all_row.source_breakdown or {}), s: cur}


def _count_reach_global(per_episode, level) -> int:
    seen = set()
    for b in per_episode.values():
        for key, v in b["max_progress"].items():
            if v + 1e-9 >= level:
                seen.add(key)
    return len(seen)


def finalize_all_row(session: Session, all_row, per_episode) -> None:
    """全站 plays/listeners 需跨节目去重，在逐节目累加后统一重算。"""
    sessions, listeners = set(), set()
    src_plays, src_listeners = defaultdict(set), defaultdict(set)
    for b in per_episode.values():
        sessions |= b["play_sessions"]
        listeners |= b["listeners"]
        for s, v in b["sources"].items():
            src_plays[s] |= v["plays"]
            src_listeners[s] |= v["listeners"]
    all_row.plays = len(sessions)
    all_row.unique_listeners = len(listeners)
    all_row.completion_rate = (all_row.completes / all_row.unique_listeners
                               if all_row.unique_listeners else None)
    all_row.avg_listen_ratio = None  # 全站无单一节目时长，口径文档注明不计算
    all_row.source_breakdown = {
        s: {"plays": len(src_plays[s]), "listeners": len(src_listeners[s])}
        for s in sorted(src_plays, key=lambda k: -len(src_plays[k]))
    }


def run(from_day: dt.date, to_day: dt.date, db_url: str,
        org_id: str = "org_demo") -> int:
    """区间回补入口；to<from 或跨度>92 天拒绝。"""
    if to_day < from_day:
        raise SystemExit("[range] --to 早于 --from，拒绝执行")
    if (to_day - from_day).days > 92:
        raise SystemExit("[range] 回补跨度超过 92 天，请分批执行")
    from sqlalchemy import create_engine
    engine = create_engine(db_url, future=True)
    total = 0
    with Session(engine) as session:
        with session.begin():
            day = from_day
            while day <= to_day:
                counts = aggregate_day(session, day, org_id)
                total += sum(counts.values())
                day += dt.timedelta(days=1)
            # finalize 全站行（需要全部节目桶：重查内存代价高，改为逐日 finalize）
        _finalize_all_rows(session, from_day, to_day, org_id)
    return total


def _finalize_all_rows(session, from_day, to_day, org_id):
    """对区间内每一天重建全站行的去重口径（plays/listeners）。"""
    day = from_day
    while day <= to_day:
        d_start = dt.datetime.combine(day, dt.time.min, tzinfo=TZ)
        d_end = d_start + dt.timedelta(days=1)
        events = session.execute(
            select(ListeningEvent).where(
                ListeningEvent.deleted_at.is_(None),
                ListeningEvent.ts >= d_start, ListeningEvent.ts < d_end)
        ).scalars().all()
        sessions, listeners, completers = set(), set(), set()
        src_plays, src_listeners = defaultdict(set), defaultdict(set)
        for ev in events:
            key = _listener_key(ev.user_id, ev.anon_id)
            if ev.event_type == "episode_view":
                continue  # 浏览不计入听众口径（与口径文档一致）
            if ev.event_type == "play_start":
                if ev.session_id:
                    sessions.add(ev.session_id)
                listeners.add(key)
                if ev.source:
                    src_plays[ev.source].add(ev.session_id or key)
                    src_listeners[ev.source].add(key)
            else:
                listeners.add(key)
                if ev.source:
                    src_listeners[ev.source].add(key)
            if ev.event_type == "complete":
                completers.add(key)
        row = session.execute(
            select(EpisodeDailyStats).where(
                EpisodeDailyStats.org_id == org_id,
                EpisodeDailyStats.episode_id == ALL_KEY,
                EpisodeDailyStats.stat_date == day)
        ).scalar_one_or_none()
        if row is not None:
            row.plays = len(sessions)
            row.unique_listeners = len(listeners)
            row.completes = len(completers)  # 全站完成听众跨节目去重
            row.completion_rate = (row.completes / row.unique_listeners
                                   if row.unique_listeners else None)
            row.source_breakdown = {
                s: {"plays": len(src_plays.get(s, set())),
                    "listeners": len(src_listeners.get(s, set()))}
                for s in sorted(set(src_plays) | set(src_listeners),
                                key=lambda k: -len(src_plays.get(k, set())))
            }
        day += dt.timedelta(days=1)
    session.commit()


def main(argv=None):
    ap = argparse.ArgumentParser(description="收听数据日汇总任务（S6-POD-040）")
    ap.add_argument("--from", dest="from_day", required=False)
    ap.add_argument("--to", dest="to_day", required=False)
    ap.add_argument("--db", default="sqlite:///podcast_demo.db")
    ap.add_argument("--org", default="org_demo")
    args = ap.parse_args(argv)
    tz_now = dt.datetime.now(TZ)
    yesterday = (tz_now - dt.timedelta(days=1)).date()
    from_day = (dt.date.fromisoformat(args.from_day) if args.from_day
                else yesterday)
    to_day = (dt.date.fromisoformat(args.to_day) if args.to_day else from_day)
    n = run(from_day, to_day, args.db, args.org)
    print(f"aggregated rows: {n} ({from_day}..{to_day})")


if __name__ == "__main__":
    main()
