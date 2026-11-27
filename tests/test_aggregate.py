# -*- coding: utf-8 -*-
"""S6-POD-040 测试：AC1 夹具对账 / AC2 幂等 / AC3 回补 7 天 / 边界。"""
import hashlib
import json
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.models import (Base, ColumnDailyStats, Episode, EpisodeDailyStats,
                        ListeningEvent)
from app.aggregate import ALL_KEY, REACH_LEVELS, aggregate_day, run

TZ = ZoneInfo("Asia/Shanghai")
FIXTURE_DB = "sqlite:///podcast_fixture.db"
EXPECTED = json.loads((ROOT / "outputs" / "expected.json").read_text(encoding="utf-8"))


def _run_range(from_day="2026-11-01", to_day="2026-11-08", db=FIXTURE_DB):
    return run(date.fromisoformat(from_day), date.fromisoformat(to_day), db)


# ---------------- AC1 ----------------
def test_ac1_fixture_vs_expected_per_field():
    _run_range()
    engine = create_engine(FIXTURE_DB, future=True)
    with Session(engine) as s:
        rows = s.execute(select(EpisodeDailyStats).where(
            EpisodeDailyStats.episode_id != ALL_KEY)).scalars().all()
        assert len(rows) == len(EXPECTED["episodes"]), "节目×日行数一致"
        for r in rows:
            exp = EXPECTED["episodes"][f"{r.episode_id}|{r.stat_date.isoformat()}"]
            assert r.views == exp["views"], (r.episode_id, r.stat_date, "views")
            assert r.plays == exp["plays"], (r.episode_id, r.stat_date, "plays")
            assert r.unique_listeners == exp["unique_listeners"]
            assert r.listen_seconds == exp["listen_seconds"]
            assert r.completes == exp["completes"]
            assert r.completion_rate == pytest.approx(exp["completion_rate"], None,
                                                      1e-9) or (
                r.completion_rate is None and exp["completion_rate"] is None)
            if exp["avg_listen_ratio"] is None:
                assert r.avg_listen_ratio is None
            else:
                assert r.avg_listen_ratio == pytest.approx(exp["avg_listen_ratio"],
                                                           abs=1e-9)
            for lv in REACH_LEVELS:
                assert getattr(r, f"reach_{lv}") == exp["reach"][f"reach_{lv}"], \
                    (r.episode_id, r.stat_date, f"reach_{lv}")
            assert r.source_breakdown == exp["source_breakdown"]

def test_ac1_column_and_all_rows_match():
    _run_range()
    engine = create_engine(FIXTURE_DB, future=True)
    with Session(engine) as s:
        cols = s.execute(select(ColumnDailyStats)).scalars().all()
        assert len(cols) == len(EXPECTED["columns"])
        for r in cols:
            exp = EXPECTED["columns"][f"{r.column_id}|{r.stat_date.isoformat()}"]
            assert (r.views, r.plays, r.unique_listeners, r.listen_seconds,
                    r.completes) == (exp["views"], exp["plays"],
                                     exp["unique_listeners"], exp["listen_seconds"],
                                     exp["completes"])
        alls = s.execute(select(EpisodeDailyStats).where(
            EpisodeDailyStats.episode_id == ALL_KEY)).scalars().all()
        assert len(alls) == len(EXPECTED["all"])
        for r in alls:
            exp = EXPECTED["all"][r.stat_date.isoformat()]
            assert r.views == exp["views"]
            assert r.plays == exp["plays"]
            assert r.unique_listeners == exp["unique_listeners"]
            assert r.listen_seconds == exp["listen_seconds"]
            assert r.completes == exp["completes"]
            assert r.completion_rate == pytest.approx(exp["completion_rate"],
                                                      None, 1e-9) or (
                r.completion_rate is None and exp["completion_rate"] is None)
            assert r.avg_listen_ratio is None
            assert r.source_breakdown == exp["source_breakdown"]

def test_ac1_expected_covers_2000plus_events_3_episodes():
    engine = create_engine(FIXTURE_DB, future=True)
    with Session(engine) as s:
        n = len(s.execute(select(ListeningEvent)).scalars().all())
        assert n >= 2000, n
        n_ep = len(s.execute(select(Episode)).scalars().all())
        assert n_ep == 3

# ---------------- AC2 ----------------
def _snapshot(db=FIXTURE_DB):
    engine = create_engine(db, future=True)
    h = hashlib.sha256()
    with Session(engine) as s:
        for model in (EpisodeDailyStats, ColumnDailyStats):
            key_col = (model.episode_id if model is EpisodeDailyStats
                       else model.column_id)
            rows = s.execute(select(model)).scalars().all()
            rows.sort(key=lambda r: (str(r.stat_date), str(key_col), r.org_id))
            for r in rows:
                d = {c: getattr(r, c) for c in r.__table__.columns.keys()
                     if c not in ("id", "created_at", "updated_at")}
                h.update(json.dumps(d, sort_keys=True, default=str,
                                    ensure_ascii=False).encode())
    return h.hexdigest()

def test_ac2_idempotent_same_day_twice():
    _run_range()
    sha1 = _snapshot()
    _run_range()  # 同一区间再跑一次
    sha2 = _snapshot()
    assert sha1 == sha2, "重复运行后汇总表逐行不变"

def test_ac2_single_day_twice_rowcount_unchanged():
    _run_range()
    engine = create_engine(FIXTURE_DB, future=True)
    with Session(engine) as s:
        n1 = len(s.execute(select(EpisodeDailyStats)).scalars().all())
    run(date(2026, 11, 3), date(2026, 11, 3), FIXTURE_DB)
    with Session(engine) as s:
        n2 = len(s.execute(select(EpisodeDailyStats)).scalars().all())
    assert n1 == n2

# ---------------- AC3 ----------------
def test_ac3_backfill_7_days_one_all_row_per_day():
    _run_range()
    run(date(2026, 11, 1), date(2026, 11, 7), FIXTURE_DB)  # 显式 7 天回补
    engine = create_engine(FIXTURE_DB, future=True)
    with Session(engine) as s:
        alls = s.execute(select(EpisodeDailyStats).where(
            EpisodeDailyStats.episode_id == ALL_KEY,
            EpisodeDailyStats.stat_date >= date(2026, 11, 1),
            EpisodeDailyStats.stat_date <= date(2026, 11, 7))).scalars().all()
        assert len(alls) == 7
        assert {r.stat_date for r in alls} == {
            date(2026, 11, 1) + __import__("datetime").timedelta(days=i)
            for i in range(7)}

def test_ac3_backfill_single_day_touches_only_that_day():
    _run_range()
    engine = create_engine(FIXTURE_DB, future=True)
    with Session(engine) as s:
        before = {r.episode_id: r.listen_seconds
                  for r in s.execute(select(EpisodeDailyStats).where(
                      EpisodeDailyStats.stat_date == date(2026, 11, 5))).scalars()}
    run(date(2026, 11, 5), date(2026, 11, 5), FIXTURE_DB)
    with Session(engine) as s:
        after = {r.episode_id: r.listen_seconds
                 for r in s.execute(select(EpisodeDailyStats).where(
                     EpisodeDailyStats.stat_date == date(2026, 11, 5))).scalars()}
    assert before == after

def test_ac3_range_validation():
    with pytest.raises(SystemExit):
        run(date(2026, 11, 5), date(2026, 11, 1), FIXTURE_DB)  # to < from

# ---------------- 边界 ----------------
def test_boundary_zero_listener_completion_null(tmp_path):
    db = f"sqlite:///{tmp_path/'t.db'}"
    engine = create_engine(db, future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        with s.begin():
            s.add(Episode(id="epX", column_id="c1", title="x", duration_sec=100))
            t = datetime(2026, 5, 1, 8, 0, tzinfo=TZ)
            s.add(ListeningEvent(episode_id="epX", event_type="episode_view",
                                 user_id="u1", source="search", ts=t))
    with Session(engine) as s:
        with s.begin():
            aggregate_day(s, date(2026, 5, 1))
    with Session(engine) as s:
        r = s.execute(select(EpisodeDailyStats).where(
            EpisodeDailyStats.episode_id == "epX")).scalar_one()
        assert r.unique_listeners == 0 and r.completion_rate is None
        assert r.avg_listen_ratio is None

def test_boundary_reach_100_exact(tmp_path):
    db = f"sqlite:///{tmp_path/'t.db'}"
    engine = create_engine(db, future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        with s.begin():
            s.add(Episode(id="epY", column_id="c1", title="y", duration_sec=600))
            t = datetime(2026, 5, 2, 9, 0, tzinfo=TZ)
            s.add(ListeningEvent(episode_id="epY", event_type="play_start",
                                 session_id="s1", user_id="u1", source="share", ts=t))
            s.add(ListeningEvent(episode_id="epY", event_type="progress",
                                 session_id="s1", user_id="u1", source="share",
                                 progress_pct=100.0, ts=t))
    with Session(engine) as s:
        with s.begin():
            aggregate_day(s, date(2026, 5, 2))
    with Session(engine) as s:
        r = s.execute(select(EpisodeDailyStats).where(
            EpisodeDailyStats.episode_id == "epY")).scalar_one()
        assert r.reach_100 == 1 and r.reach_90 == 1
        assert r.source_breakdown == {"share": {"plays": 1, "listeners": 1}}
