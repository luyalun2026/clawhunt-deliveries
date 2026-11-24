"""归因引擎：直连归因 + 相关推荐辅助归因（24h 闭区间、最近点击优先、去重）。

时间一律 UTC 存储；统计日按 Asia/Shanghai 切分，辅助转化归「点击日」所在期。
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Iterable

SHANGHAI = dt.timezone(dt.timedelta(hours=8))
WINDOW = dt.timedelta(hours=24)

ITEM_TO_COLUMN = {
    "event": "assisted_event_signups",
    "course": "assisted_course_signups",
    "opportunity": "assisted_opportunity_requests",
}


def _parse(value) -> dt.datetime:
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)
    return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def local_date(value) -> dt.date:
    return _parse(value).astimezone(SHANGHAI).date()


def direct_counts(intro_requests: Iterable[dict]) -> dict[tuple[str, dt.date], dict[str, int]]:
    """直连归因：三态为累计漏斗 submitted ⊇ staff_approved ⊇ accepted。"""
    raw: dict[tuple[str, dt.date], dict[str, set[str]]] = defaultdict(
        lambda: {"submitted": set(), "staff_approved": set(), "accepted": set()})

    for req in intro_requests:
        key = (str(req["episode_id"]), local_date(req["created_at"]))
        req_id = str(req.get("request_id") or req.get("id"))
        raw[key]["submitted"].add(req_id)
        status = (req.get("status") or "submitted").lower()
        if status in ("staff_approved", "accepted"):
            raw[key]["staff_approved"].add(req_id)
        if status == "accepted":
            raw[key]["accepted"].add(req_id)

    out: dict[tuple[str, dt.date], dict[str, int]] = {}
    for key, sets in raw.items():
        # 脏数据兜底：accepted 必须是 approved 的子集
        approved = sets["staff_approved"] | sets["accepted"]
        out[key] = {
            "intro_requests": len(sets["submitted"]),
            "intro_staff_approved": len(approved),
            "intro_accepted": len(sets["accepted"]),
        }
    return out


def assisted_counts(clicks: Iterable[dict], conversions: Iterable[dict]) -> tuple[
        dict[tuple[str, dt.date], dict[str, int]], list[str]]:
    """辅助归因：24h 闭区间内匹配 (user_id, item_type, item_id)，多期竞争归最近点击。"""
    warnings: list[str] = []
    seen_clicks: set[str] = set()
    deduped: list[dict] = []
    for click in clicks:
        cid = str(click.get("click_id") or f"{click['user_id']}|{click['episode_id']}|{click['item_id']}|{click['clicked_at']}")
        if cid in seen_clicks:
            warnings.append(f"重复上报点击已去重：{cid}")
            continue
        seen_clicks.add(cid)
        deduped.append(click)

    by_item: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for click in deduped:
        by_item[(str(click["user_id"]), click["item_type"], str(click["item_id"]))].append(click)

    counted: set[tuple] = set()
    out: dict[tuple[str, dt.date], dict[str, int]] = defaultdict(
        lambda: {col: 0 for col in ITEM_TO_COLUMN.values()})

    for conv in conversions:
        key = (str(conv["user_id"]), conv["item_type"], str(conv["item_id"]))
        converted_at = _parse(conv["converted_at"])
        candidates = [
            c for c in by_item.get(key, [])
            if _parse(c["clicked_at"]) <= converted_at <= _parse(c["clicked_at"]) + WINDOW
        ]
        if not candidates:
            continue
        winner = max(candidates, key=lambda c: _parse(c["clicked_at"]))
        dedupe_key = (key, converted_at, str(winner["episode_id"]))
        if dedupe_key in counted:
            continue
        counted.add(dedupe_key)
        column = ITEM_TO_COLUMN[winner["item_type"]]
        out[(str(winner["episode_id"]), local_date(winner["clicked_at"]))][column] += 1
    return dict(out), warnings


def merge(direct: dict, assisted: dict) -> dict[tuple[str, dt.date], dict[str, int]]:
    rows: dict[tuple[str, dt.date], dict[str, int]] = defaultdict(
        lambda: {
            "intro_requests": 0, "intro_staff_approved": 0, "intro_accepted": 0,
            "assisted_event_signups": 0, "assisted_course_signups": 0,
            "assisted_opportunity_requests": 0,
        })
    for source in (direct, assisted):
        for key, values in source.items():
            rows[key].update({k: rows[key].get(k, 0) + v for k, v in values.items()})
    return dict(rows)


def ensure_episode_rows(rows: dict, episode_ids: Iterable[str],
                        stat_date: dt.date) -> dict:
    """无转化数据的节目也输出 0 行（不停更），按点击/请求日期补位。"""
    filled = dict(rows)
    for ep in episode_ids:
        if not any(key[0] == str(ep) and key[1] == stat_date for key in filled):
            filled[(str(ep), stat_date)] = {
                "intro_requests": 0, "intro_staff_approved": 0, "intro_accepted": 0,
                "assisted_event_signups": 0, "assisted_course_signups": 0,
                "assisted_opportunity_requests": 0,
            }
    return filled
