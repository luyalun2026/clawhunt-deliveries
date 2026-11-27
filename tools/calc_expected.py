# -*- coding: utf-8 -*-
"""独立期望值计算器：用朴素字典遍历（与主实现不同代码路径）手算期望值 → expected.json。

独立实现口径：
  views       episode_view 计数
  plays       play_start 的 session 去重
  listeners   user_id 优先 / anon_id 兜底 去重
  listen_sec  played_delta_sec 求和
  completes   有 complete 的去重听众
  comp_rate   completes / listeners（0 → null）
  avg_ratio   listen_sec / (listeners × duration)（缺时长 → null）
  reach_N     听众级最大进度 ≥ N 去重计数
  source_bd   {source: {plays: session 去重, listeners: 去重}} 按 plays 降序
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

import datetime as dt

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models import Base, Episode, EpisodeDailyStats, ListeningEvent

TZ = ZoneInfo("Asia/Shanghai")
ALL_KEY = "__ALL__"
LEVELS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]


def _key(user_id, anon_id):
    return ("u", user_id) if user_id else ("a", anon_id)


def calc(db_url: str = "sqlite:///podcast_fixture.db") -> dict:
    engine = create_engine(db_url, future=True)
    out = {"episodes": {}, "columns": {}, "all": {}}
    with Session(engine) as s:
        eps = {e.id: (e.column_id, e.duration_sec)
               for e in s.execute(select(Episode)).scalars()}
        events = s.execute(select(ListeningEvent)).scalars().all()
        days = sorted({e.ts.astimezone(TZ).date() for e in events})
        for day in days:
            eps_day = defaultdict(lambda: {
                "views": 0, "sessions": set(), "listeners": set(),
                "sec": 0, "comp": set(), "prog": defaultdict(float),
                "src_p": defaultdict(set), "src_l": defaultdict(set)})
            for e in events:
                if e.ts.astimezone(TZ).date() != day:
                    continue
                b = eps_day[e.episode_id]
                k = _key(e.user_id, e.anon_id)
                if e.event_type == "episode_view":
                    b["views"] += 1
                elif e.event_type == "play_start":
                    if e.session_id:
                        b["sessions"].add(e.session_id)
                    b["listeners"].add(k)
                    if e.source:
                        b["src_p"][e.source].add(e.session_id or k)
                        b["src_l"][e.source].add(k)
                elif e.event_type == "progress":
                    b["listeners"].add(k)
                    if e.progress_pct is not None:
                        b["prog"][k] = max(b["prog"][k], e.progress_pct)
                    if e.source:
                        b["src_l"][e.source].add(k)
                elif e.event_type == "complete":
                    b["listeners"].add(k)
                    b["comp"].add(k)
                    if e.source:
                        b["src_l"][e.source].add(k)
                if e.played_delta_sec:
                    b["sec"] += e.played_delta_sec
            day_s = day.isoformat()
            for ep_id, b in eps_day.items():
                col_id, dur = eps[ep_id]
                row = _row(b, dur)
                out["episodes"][f"{ep_id}|{day_s}"] = {**row, "column_id": col_id}
            # 栏目
            cols = defaultdict(lambda: {
                "views": 0, "sessions": set(), "listeners": set(),
                "sec": 0, "comp": set()})
            for ep_id, b in eps_day.items():
                c = cols[eps[ep_id][0]]
                c["views"] += b["views"]
                c["sessions"] |= b["sessions"]
                c["listeners"] |= b["listeners"]
                c["sec"] += b["sec"]
                c["comp"] |= b["comp"]
            for col_id, c in cols.items():
                n = len(c["listeners"])
                out["columns"][f"{col_id}|{day_s}"] = {
                    "views": c["views"], "plays": len(c["sessions"]),
                    "unique_listeners": n, "listen_seconds": c["sec"],
                    "completes": len(c["comp"]),
                    "completion_rate": (len(c["comp"]) / n) if n else None}
            # 全站（跨节目去重）
            sessions, listeners = set(), set()
            sp, sl = defaultdict(set), defaultdict(set)
            sec = 0
            views = 0
            comp = set()
            global_prog = defaultdict(float)
            for ep_id, b in eps_day.items():
                views += b["views"]
                sessions |= b["sessions"]
                listeners |= b["listeners"]
                sec += b["sec"]
                comp |= b["comp"]
                for k, v in b["prog"].items():
                    global_prog[k] = max(global_prog[k], v)
                for src, vs in b["src_p"].items():
                    sp[src] |= vs
                for src, vs in b["src_l"].items():
                    sl[src] |= vs
            n = len(listeners)
            out["all"][day_s] = {
                "views": views, "plays": len(sessions), "unique_listeners": n,
                "listen_seconds": sec, "completes": len(comp),
                "completion_rate": (len(comp) / n) if n else None,
                "avg_listen_ratio": None,
                "reach": {f"reach_{lv}": sum(1 for v in global_prog.values()
                                             if v + 1e-9 >= lv) for lv in LEVELS},
                "source_breakdown": {src: {"plays": len(sp.get(src, set())),
                                           "listeners": len(sl.get(src, set()))}
                                     for src in sorted(set(sp) | set(sl),
                                                       key=lambda k: -len(sp.get(k, set())))}}
    return out


def _row(b, dur):
    n = len(b["listeners"])
    return {"views": b["views"], "plays": len(b["sessions"]),
            "unique_listeners": n, "listen_seconds": b["sec"],
            "completes": len(b["comp"]),
            "completion_rate": (len(b["comp"]) / n) if n else None,
            "avg_listen_ratio": (b["sec"] / (n * dur)) if (dur and n) else None,
            "reach": {f"reach_{lv}": sum(1 for v in b["prog"].values()
                                         if v + 1e-9 >= lv) for lv in LEVELS},
            "source_breakdown": {src: {"plays": len(b["src_p"].get(src, set())),
                                       "listeners": len(b["src_l"].get(src, set()))}
                                 for src in sorted(set(b["src_p"]) | set(b["src_l"]),
                                                   key=lambda k: -len(b["src_p"].get(k, set())))}}


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "sqlite:///podcast_fixture.db"
    data = calc(url)
    dest = Path(__file__).resolve().parents[1] / "outputs" / "expected.json"
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    n_ep = len(data["episodes"])
    print(f"expected.json written: {n_ep} episode-day rows, "
          f"{len(data['columns'])} column-day, {len(data['all'])} all-day")
