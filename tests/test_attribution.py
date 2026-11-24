import datetime as dt
import pathlib
import sys
import uuid
from collections import Counter

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.podcast.attribution import (  # noqa: E402
    assisted_counts, direct_counts, ensure_episode_rows, merge,
)
from app.podcast.models import Base, EpisodeConversionStat  # noqa: E402
from app.podcast.summary_job import read_rows, run_day, run_range  # noqa: E402

ORG = uuid.UUID("22222222-2222-2222-2222-222222222222")
SITE = uuid.UUID("11111111-1111-1111-1111-111111111111")
DAY = dt.date(2026, 12, 1)
T0 = "2026-12-01T02:00:00Z"   # 北京时间 10:00


@pytest.fixture()
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def click(user, episode, item_type, item_id, at, click_id=None):
    return {"click_id": click_id or f"{user}-{episode}-{item_id}-{at}", "user_id": user,
            "episode_id": episode, "item_type": item_type, "item_id": item_id,
            "clicked_at": at}


def conv(user, item_type, item_id, at):
    return {"user_id": user, "item_type": item_type, "item_id": item_id, "converted_at": at}


def test_window_23h_counted_25h_excluded():
    clicks = [
        click("u1", "EP1", "event", "E1", T0),
        click("u2", "EP1", "event", "E2", T0),
        click("u3", "EP1", "event", "E3", T0),
    ]
    conversions = [
        conv("u1", "event", "E1", "2026-12-02T01:00:00Z"),   # +23h 计入
        conv("u2", "event", "E2", "2026-12-02T03:00:00Z"),   # +25h 不计
        conv("u3", "event", "E3", "2026-12-02T02:00:00Z"),   # +24h 整，闭区间计入
    ]
    result, _ = assisted_counts(clicks, conversions)
    assert result[("EP1", DAY)]["assisted_event_signups"] == 2


def test_window_second_level_boundary():
    clicks = [click("u1", "EP1", "course", "C1", T0), click("u2", "EP1", "course", "C2", T0)]
    conversions = [
        conv("u1", "course", "C1", "2026-12-02T02:00:00Z"),       # 24h00m00s 计入
        conv("u2", "course", "C2", "2026-12-02T02:00:01Z"),       # 24h00m01s 不计
    ]
    result, _ = assisted_counts(clicks, conversions)
    assert result[("EP1", DAY)]["assisted_course_signups"] == 1


def test_competing_clicks_attributed_to_latest():
    clicks = [
        click("u4", "EP1", "event", "E9", "2026-12-01T02:00:00Z"),
        click("u4", "EP2", "event", "E9", "2026-12-01T05:00:00Z"),
    ]
    conversions = [conv("u4", "event", "E9", "2026-12-01T08:00:00Z")]
    result, _ = assisted_counts(clicks, conversions)
    assert result[("EP2", DAY)]["assisted_event_signups"] == 1
    assert ("EP1", DAY) not in result or result[("EP1", DAY)]["assisted_event_signups"] == 0


def test_latest_click_outside_window_falls_back():
    """最近一次点击已超 24h，则退回到窗口内更早的那次点击。"""
    clicks = [
        click("u5", "EP1", "event", "E7", "2026-12-01T02:00:00Z"),
        click("u5", "EP2", "event", "E7", "2026-12-03T02:00:00Z"),
    ]
    conversions = [conv("u5", "event", "E7", "2026-12-02T01:00:00Z")]
    result, _ = assisted_counts(clicks, conversions)
    assert result[("EP1", DAY)]["assisted_event_signups"] == 1


def test_intro_counts_match_source_table():
    requests = [
        {"id": "r1", "episode_id": "EP1", "status": "accepted", "created_at": "2026-12-01T03:00:00Z"},
        {"id": "r2", "episode_id": "EP1", "status": "staff_approved", "created_at": "2026-12-01T04:00:00Z"},
        {"id": "r3", "episode_id": "EP1", "status": "submitted", "created_at": "2026-12-01T05:00:00Z"},
        {"id": "r4", "episode_id": "EP2", "status": "submitted", "created_at": "2026-12-01T06:00:00Z"},
    ]
    direct = direct_counts(requests)
    # 与源表 GROUP BY 对拍
    submitted = Counter(r["episode_id"] for r in requests)
    approved = Counter(r["episode_id"] for r in requests if r["status"] in ("staff_approved", "accepted"))
    accepted = Counter(r["episode_id"] for r in requests if r["status"] == "accepted")
    for ep in ("EP1", "EP2"):
        row = direct[(ep, DAY)]
        assert row["intro_requests"] == submitted[ep]
        assert row["intro_staff_approved"] == approved[ep]
        assert row["intro_accepted"] == accepted[ep]
    assert direct[("EP1", DAY)] == {"intro_requests": 3, "intro_staff_approved": 2, "intro_accepted": 1}


def test_dirty_data_accepted_without_approval():
    requests = [{"id": "r9", "episode_id": "EP3", "status": "accepted",
                 "created_at": "2026-12-01T03:00:00Z"}]
    row = direct_counts(requests)[("EP3", DAY)]
    assert row["intro_accepted"] == 1 and row["intro_staff_approved"] == 1


def test_cross_month_attributed_to_click_day():
    clicks = [click("u6", "EP1", "event", "E5", "2026-12-31T12:00:00Z")]
    conversions = [conv("u6", "event", "E5", "2027-01-01T02:00:00Z")]  # 14h 后
    result, _ = assisted_counts(clicks, conversions)
    # 北京时间 12-31 20:00 点击、01-01 10:00 转化（14h 内）→ 归点击日 12-31
    assert ("EP1", dt.date(2026, 12, 31)) in result
    assert ("EP1", dt.date(2027, 1, 1)) not in result


def test_event_and_course_counted_separately():
    clicks = [
        click("u7", "EP1", "event", "E4", T0),
        click("u7", "EP1", "course", "C4", T0),
    ]
    conversions = [
        conv("u7", "event", "E4", "2026-12-01T06:00:00Z"),
        conv("u7", "course", "C4", "2026-12-01T06:00:00Z"),
    ]
    result, _ = assisted_counts(clicks, conversions)
    row = result[("EP1", DAY)]
    assert row["assisted_event_signups"] == 1 and row["assisted_course_signups"] == 1


def test_duplicate_click_deduped():
    same = click("u8", "EP1", "event", "E8", T0, click_id="dup-1")
    result, warnings = assisted_counts([same, dict(same)], [conv("u8", "event", "E8", "2026-12-01T06:00:00Z")])
    assert result[("EP1", DAY)]["assisted_event_signups"] == 1
    assert warnings


def test_episode_without_data_emits_zero_row():
    rows = ensure_episode_rows({}, ["EP9"], DAY)
    assert rows[("EP9", DAY)]["assisted_event_signups"] == 0


def test_run_day_and_rerun_idempotent(session):
    clicks = [click("u1", "EP1", "event", "E1", T0)]
    conversions = [conv("u1", "event", "E1", "2026-12-01T06:00:00Z")]
    requests = [{"id": "r1", "episode_id": "EP1", "status": "submitted",
                 "created_at": "2026-12-01T03:00:00Z"}]
    kwargs = dict(org_id=ORG, site_id=SITE, clicks=clicks, conversions=conversions,
                  intro_requests=requests, episodes=["EP1", "EP2"])
    first = run_day(session, DAY, **kwargs)
    rows1 = read_rows(session)
    second = run_day(session, DAY, **kwargs)
    assert rows1 == read_rows(session)
    assert first["rows"] == second["rows"] == 2
    ep1 = [r for r in rows1 if r[0] == "EP1"][0]
    assert ep1[2:] == (1, 0, 0, 1, 0, 0)  # submitted 状态：只计请求数


def test_run_range_backfill(session):
    clicks = [click("u1", "EP1", "event", "E1", T0),
              click("u2", "EP1", "event", "E2", "2026-12-03T02:00:00Z")]
    conversions = [conv("u1", "event", "E1", "2026-12-01T06:00:00Z"),
                   conv("u2", "event", "E2", "2026-12-03T06:00:00Z")]
    out = run_range(session, dt.date(2026, 12, 1), dt.date(2026, 12, 3),
                    org_id=ORG, site_id=SITE, clicks=clicks, conversions=conversions,
                    intro_requests=[], episodes=["EP1"])
    assert len(out) == 3
    rows = read_rows(session)
    assert sum(r[5] for r in rows) == 2


def test_merge_sums_sources():
    merged = merge({("EP1", DAY): {"intro_requests": 2, "intro_staff_approved": 1, "intro_accepted": 0}},
                   {("EP1", DAY): {"assisted_event_signups": 3}})
    row = merged[("EP1", DAY)]
    assert row["intro_requests"] == 2 and row["assisted_event_signups"] == 3
    assert row["assisted_course_signups"] == 0
