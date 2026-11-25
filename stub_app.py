# -*- coding: utf-8 -*-
"""接口桩：会员画像接口 / 驾驶舱月活指标接口 / 互动明细接口。
对齐 S2-CRM / S3-DASH / S3-TRK 契约先行的约定；生产替换仅改 base_url。
"""
import datetime as dt
import os
import sqlite3
import sys
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from loop4_common import INTERACTION_TYPES

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts", "loop4.db")
TOKEN = "loop4-test-token"

app = FastAPI(title="会员空间平台接口桩(loop4)")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def month_bounds(month=None):
    today = dt.date.today()
    first = today.replace(day=1) if not month else dt.date.fromisoformat(month + "-01")
    nxt = (first.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return first.isoformat() + "T00:00:00", nxt.isoformat() + "T00:00:00"


def _counts_for_member(cur, member_id, lo, hi):
    """企业维度当月有效互动计数（软删除会员排除，纯浏览排除，重复签到已由索引去重）。"""
    row = cur.execute(
        "SELECT m.enterprise_id FROM members m WHERE m.id=? AND m.deleted_at IS NULL",
        (member_id,)).fetchone()
    if not row:
        return None
    ent = row["enterprise_id"]
    cnt = defaultdict(int)
    esc = 0
    for r in cur.execute(
            "SELECT type, escalated FROM interactions WHERE member_id=? AND type IN (%s) "
            "AND deleted_at IS NULL AND occurred_at >= ? AND occurred_at < ?" % ",".join("?" * len(INTERACTION_TYPES)),
            [member_id] + INTERACTION_TYPES + [lo, hi]):
        cnt[r["type"]] += 1
        esc += r["escalated"]
    return ent, {
        "certified_contacts": cnt["auth"],
        "demands": cnt["demand"],
        "signups": cnt["signup"],
        "checkins": cnt["checkin"],
        "asks": cnt["ask"],
        "escalations": esc,
    }


@app.get("/api/crm/members/{member_id}/portrait")
def portrait(member_id: str, authorization: str = Header(default="")):
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "unauthorized")
    conn = db()
    cur = conn.cursor()
    lo, hi = month_bounds()
    res = _counts_for_member(cur, member_id, lo, hi)
    conn.close()
    if not res:
        raise HTTPException(404, "member not found or deleted")
    ent, counts = res
    return JSONResponse({"member_id": member_id, "enterprise_id": ent,
                         "month_counts": counts,
                         "source": "mini"})


@app.get("/api/dash/mau")
def mau(month: str = "", authorization: str = Header(default="")):
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "unauthorized")
    conn = db()
    cur = conn.cursor()
    lo, hi = month_bounds(month or None)
    active = set()
    total_ents = {r["id"] for r in cur.execute("SELECT id FROM enterprises")}
    for r in cur.execute(
            "SELECT DISTINCT m.enterprise_id FROM interactions i JOIN members m ON m.id=i.member_id "
            "WHERE i.type IN (%s) AND i.deleted_at IS NULL AND m.deleted_at IS NULL "
            "AND i.occurred_at >= ? AND i.occurred_at < ?" % ",".join("?" * len(INTERACTION_TYPES)),
            INTERACTION_TYPES + [lo, hi]):
        active.add(r["enterprise_id"])
    conn.close()
    denom = len(total_ents)
    return JSONResponse({"month": (month or dt.date.today().isoformat()[:7]),
                         "active_enterprises": sorted(active),
                         "numerator": len(active), "denominator": denom,
                         "ratio": round(len(active) / denom, 4) if denom else 0.0})


@app.get("/api/track/interactions")
def interactions(member_id: str = "", authorization: str = Header(default="")):
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "unauthorized")
    conn = db()
    cur = conn.cursor()
    lo, hi = month_bounds()
    rows = cur.execute(
        "SELECT i.type, i.source, i.activity_id, i.escalated, i.occurred_at "
        "FROM interactions i JOIN members m ON m.id=i.member_id "
        "WHERE (?='' OR i.member_id=?) AND i.deleted_at IS NULL AND m.deleted_at IS NULL "
        "AND i.occurred_at >= ? AND i.occurred_at < ? ORDER BY i.id",
        (member_id, member_id, lo, hi)).fetchall()
    conn.close()
    return JSONResponse({"items": [dict(r) for r in rows]})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8931)
