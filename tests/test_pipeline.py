import datetime as dt
import json
import pathlib
import sys

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.analytics.models import Base, FunnelDailyStat, MonthlyActiveCompany, PageDailyStat  # noqa: E402
from app.analytics.pipeline import aggregate, read_funnel_stats, read_page_stats, run_day  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVENTS = json.loads((ROOT / "fixtures" / "events.json").read_text(encoding="utf-8"))
DAY = dt.date(2026, 12, 1)
SITE = "11111111-1111-1111-1111-111111111111"
ORG = "22222222-2222-2222-2222-222222222222"

# 手算期望值（不来自实现）：先写入测试，再与实现结果对拍
EXPECTED_PAGES = {
    "pages/home/index": (7, 2),      # c1 五次 + c2 匿名/认证各一次；uv = c1 + a2
    "pages/mine/index": (1, 1),
    "pages/resource/index": (1, 1),
}
EXPECTED_FUNNELS = {
    ("resource_connect", "-", "resource_view"): 8,
    ("resource_connect", "-", "connect_request"): 3,
    ("event_attendance", "E1", "event_view"): 6,
    ("event_attendance", "E1", "event_register"): 4,
    ("event_attendance", "E1", "event_checkin"): 3,
    ("auth", "-", "app_launch"): 9,
    ("auth", "-", "auth_apply"): 5,
    ("auth", "-", "auth_success"): 2,
}


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _uuid(text: str):
    import uuid
    return uuid.UUID(text)


def test_funnel_counts_match_hand_calc(session):
    run_day(session, EVENTS, DAY, _uuid(SITE), _uuid(ORG))
    got = {(a, b, c): d for a, b, c, d in read_funnel_stats(session)}
    assert got == EXPECTED_FUNNELS


def test_page_pv_uv(session):
    run_day(session, EVENTS, DAY, _uuid(SITE), _uuid(ORG))
    got = {page: (pv, uv) for _, page, pv, uv in read_page_stats(session)}
    assert got == EXPECTED_PAGES


def test_uv_dedup_same_user_multiple_visits(session):
    """同一人同日同页 5 次 PV 只计 1 uv；匿名转认证不重复计数。"""
    run_day(session, EVENTS, DAY, _uuid(SITE), _uuid(ORG))
    rows = {p: (pv, uv) for _, p, pv, uv in read_page_stats(session)}
    assert rows["pages/home/index"] == (7, 2)
    home = session.execute(
        select(PageDailyStat).where(PageDailyStat.page == "pages/home/index")
    ).scalar_one()
    assert home.uv == 2 < home.pv


def test_rerun_idempotent(session):
    run_day(session, EVENTS, DAY, _uuid(SITE), _uuid(ORG))
    first_pages = read_page_stats(session)
    first_funnels = read_funnel_stats(session)
    count1 = session.query(PageDailyStat).count() + session.query(FunnelDailyStat).count()
    run_day(session, EVENTS, DAY, _uuid(SITE), _uuid(ORG))
    count2 = session.query(PageDailyStat).count() + session.query(FunnelDailyStat).count()
    assert first_pages == read_page_stats(session)
    assert first_funnels == read_funnel_stats(session)
    assert count1 == count2


def test_monthly_active_excludes_browse_only(session):
    run_day(session, EVENTS, DAY, _uuid(SITE), _uuid(ORG))
    actives = {r.company_pid for r in session.execute(select(MonthlyActiveCompany)).scalars()}
    # compA/compB 都有有效互动（对接/报名/签到/认证）；纯浏览的 c9 属 compB，不改变集合
    assert actives == {"compA", "compB"}


def test_boundary_midnight_split(session):
    """23:59:59 与次日 00:00:00 分属两天。"""
    base = {
        "site_id": SITE, "org_id": ORG, "contact_id": "c1",
        "company_pid": "compA", "page": "pages/home/index", "event_id": None,
    }
    events = [
        dict(base, event_type="page_view", occurred_at="2026-12-01T15:59:59Z"),  # 北京 23:59:59
        dict(base, event_type="page_view", occurred_at="2026-12-01T16:00:00Z"),  # 北京次日 00:00
    ]
    pages_d1, _ = aggregate(events, dt.date(2026, 12, 1), _uuid(SITE), _uuid(ORG))
    pages_d2, _ = aggregate(events, dt.date(2026, 12, 2), _uuid(SITE), _uuid(ORG))
    assert [r["pv"] for r in pages_d1] == [1]
    assert [r["pv"] for r in pages_d2] == [1]


def test_empty_day_writes_no_rows(session):
    stats = run_day(session, EVENTS, dt.date(2026, 12, 5), _uuid(SITE), _uuid(ORG))
    assert stats["page_rows"] == 0 and stats["funnel_rows"] == 0


def test_site_isolation(session):
    other = "33333333-3333-3333-3333-333333333333"
    run_day(session, EVENTS, DAY, _uuid(SITE), _uuid(ORG))
    run_day(session, EVENTS, DAY, _uuid(other), _uuid(ORG))
    home_site = session.execute(
        select(PageDailyStat).where(PageDailyStat.page == "pages/home/index",
                                  PageDailyStat.site_id == _uuid(SITE))
    ).scalar_one()
    assert home_site.pv == 7


def test_strict_funnel_mode(monkeypatch):
    """STRICT_FUNNEL=1 时按集合交集统计：认证漏斗第 3 步仍为 2（子集关系本就成立）。"""
    import importlib
    import app.analytics.pipeline as pl
    monkeypatch.setenv("STRICT_FUNNEL", "1")
    importlib.reload(pl)
    _, funnels = pl.aggregate(EVENTS, DAY, _uuid(SITE), _uuid(ORG))
    got = {(r["funnel_code"], r["scope_key"], r["step_key"]): r["user_count"] for r in funnels}
    assert got[("auth", "-", "auth_success")] == 2
    assert got[("resource_connect", "-", "connect_request")] == 3
    monkeypatch.delenv("STRICT_FUNNEL")
    importlib.reload(pl)
