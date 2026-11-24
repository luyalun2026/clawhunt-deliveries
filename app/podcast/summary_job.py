"""日汇总任务：attribution → episode_conversion_stats（幂等，可回补）。

用法：
  python summary_job.py --date 2026-12-01
  python summary_job.py --from 2026-12-01 --to 2026-12-07
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import uuid
from typing import Iterable

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from .attribution import assisted_counts, direct_counts, ensure_episode_rows, merge
from .models import EpisodeConversionStat


def run_day(session: Session, stat_date: dt.date, *, org_id: uuid.UUID, site_id: uuid.UUID,
            clicks: list[dict], conversions: list[dict], intro_requests: list[dict],
            episodes: Iterable[str]) -> dict:
    direct = direct_counts(intro_requests)
    assisted, warnings = assisted_counts(clicks, conversions)
    rows = merge(direct, assisted)
    rows = ensure_episode_rows(rows, episodes, stat_date)

    payload = []
    for (episode_id, day), values in rows.items():
        if day != stat_date:
            continue
        payload.append({
            "id": uuid.uuid4(), "org_id": org_id, "site_id": site_id,
            "episode_id": episode_id, "stat_date": day, **values,
        })

    session.execute(delete(EpisodeConversionStat).where(
        EpisodeConversionStat.stat_date == stat_date,
        EpisodeConversionStat.site_id == site_id,
    ))
    if payload:
        session.execute(insert(EpisodeConversionStat), payload)
    return {"rows": len(payload), "warnings": warnings}


def run_range(session: Session, start: dt.date, end: dt.date, **kwargs) -> list[dict]:
    out = []
    day = start
    while day <= end:
        out.append(run_day(session, day, **kwargs))
        day += dt.timedelta(days=1)
    return out


def read_rows(session: Session) -> list[tuple]:
    stmt = select(
        EpisodeConversionStat.episode_id, EpisodeConversionStat.stat_date,
        EpisodeConversionStat.intro_requests, EpisodeConversionStat.intro_staff_approved,
        EpisodeConversionStat.intro_accepted, EpisodeConversionStat.assisted_event_signups,
        EpisodeConversionStat.assisted_course_signups,
        EpisodeConversionStat.assisted_opportunity_requests,
    ).order_by(EpisodeConversionStat.episode_id, EpisodeConversionStat.stat_date)
    return [tuple(r) for r in session.execute(stmt).all()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--from")
    ap.add_argument("--to")
    args = ap.parse_args()
    print("summary_job: 需注入数据源（fixtures 或真实查询桩），见 README")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
