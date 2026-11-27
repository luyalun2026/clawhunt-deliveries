# -*- coding: utf-8 -*-
"""虚构事件夹具生成器（固定种子，≥2000 条，3 期节目 × 7 天）。

输出 sqlite 夹具库：episodes + listening_events。
边界覆盖：anon_id 听众、跨午夜 session、缺时长节目、进度恰好 100%、
同听众多设备、未知 source。
"""
from __future__ import annotations

import datetime as dt
import random
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, Episode, ListeningEvent

TZ = ZoneInfo("Asia/Shanghai")
SEED = 20261127
DAYS = [dt.date(2026, 11, 1) + dt.timedelta(days=i) for i in range(7)]

EPISODES = [
    ("ep_A", "col_tech", "虚构节目 A · 科技访谈", 3600),
    ("ep_B", "col_biz", "虚构节目 B · 商业观察", 2400),
    ("ep_C", "col_tech", "虚构节目 C · 深夜电台", None),  # 缺时长
]
SOURCES = ["search", "share", "recommend", "push", "unknown_src"]


def build(db_url: str = "sqlite:///podcast_fixture.db") -> int:
    engine = create_engine(db_url, future=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    rng = random.Random(SEED)
    rows = 0
    with Session(engine) as session:
        with session.begin():
            for eid, col, title, dur in EPISODES:
                session.add(Episode(id=eid, column_id=col, title=title,
                                    duration_sec=dur))
            for day in DAYS:
                n_users = rng.randint(28, 40)
                users = [f"user_{i:03d}" for i in range(n_users)]
                anons = [f"anon_{i:03d}" for i in range(8)]
                for eid, col, title, dur in EPISODES:
                    n_view = rng.randint(20, 34)
                    for _ in range(n_view):
                        who = rng.choice(users + anons)
                        uid = who if who.startswith("user_") else None
                        anon = who if who.startswith("anon_") else None
                        t = dt.datetime.combine(day, dt.time(0, 0),
                                                tzinfo=TZ) + dt.timedelta(
                            minutes=rng.choice(range(6, 1440, 7)))
                        session.add(ListeningEvent(
                            episode_id=eid, event_type="episode_view",
                            user_id=uid, anon_id=anon, source=rng.choice(SOURCES),
                            ts=t))
                        rows += 1
                    # 播放会话：部分跨午夜（前一天 23:40 起，progress 落在次日）
                    n_play = rng.randint(15, 25)
                    for i in range(n_play):
                        who = rng.choice(users + anons)
                        uid = who if who.startswith("user_") else None
                        anon = who if who.startswith("anon_") else None
                        src = rng.choice(SOURCES)
                        sid = f"s_{day.strftime('%m%d')}_{eid[-1]}_{i:03d}"
                        base = dt.datetime.combine(day, dt.time(0, 0), tzinfo=TZ) + \
                            dt.timedelta(minutes=rng.choice(range(5, 1430, 11)))
                        if rng.random() < 0.05:  # 跨午夜 session
                            base = base.replace(hour=23, minute=40)
                        session.add(ListeningEvent(
                            episode_id=eid, event_type="play_start",
                            session_id=sid, user_id=uid, anon_id=anon,
                            source=src, ts=base))
                        rows += 1
                        # progress 若干次（含恰好 100%）
                        for k in range(rng.randint(2, 5)):
                            prog = 100.0 if rng.random() < 0.08 else round(
                                rng.uniform(3, 97), 1)
                            delta = rng.randint(10, 600)
                            t = base + dt.timedelta(seconds=delta * (k + 1))
                            session.add(ListeningEvent(
                                episode_id=eid, event_type="progress",
                                session_id=sid, user_id=uid, anon_id=anon,
                                source=src, played_delta_sec=delta,
                                progress_pct=prog, ts=t))
                            rows += 1
                        if rng.random() < 0.35:
                            t = base + dt.timedelta(minutes=rng.randint(10, 50))
                            session.add(ListeningEvent(
                                episode_id=eid, event_type="complete",
                                session_id=sid, user_id=uid, anon_id=anon,
                                source=src, ts=t))
                            rows += 1
    return rows


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "sqlite:///podcast_fixture.db"
    n = build(url)
    print(f"fixture built: {n} events, 3 episodes, 7 days -> {url}")
