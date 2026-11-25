# -*- coding: utf-8 -*-
"""loop4 场景种子数据构造。用法：
  python seed.py --scenario loop4          # 构造（幂等，自动先 reset）
  python seed.py --reset                   # 仅清库
数据库固定为 artifacts/loop4.db（SQLite），README 写明 PG16 对接点。
"""
import argparse
import datetime as dt
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from loop4_common import ENT_A, ENT_B, MEMBER_U1, MEMBER_U2, MEMBER_UD, ACTIVITY_1, ACTIVITY_2

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts", "loop4.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS enterprises (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, site_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS members (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, enterprise_id TEXT NOT NULL,
    certified INTEGER NOT NULL DEFAULT 0, deleted_at TEXT);
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT NOT NULL, type TEXT NOT NULL, source TEXT NOT NULL,
    activity_id TEXT, escalated INTEGER NOT NULL DEFAULT 0,
    occurred_at TEXT NOT NULL, deleted_at TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS ux_checkin
    ON interactions(member_id, type, activity_id)
    WHERE type='checkin' AND deleted_at IS NULL;
"""


def reset():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    for t in ("enterprises", "members", "interactions"):
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def now_month_day(d):
    """当月某日 10:00（固定日避免跨月漂移）。上月用 28 天前。"""
    return d.isoformat() + "T10:00:00"


def seed_scenario_loop4():
    conn = reset()
    cur = conn.cursor()
    for e in (ENT_A, ENT_B):
        cur.execute("INSERT INTO enterprises VALUES (?,?,?)", (e["id"], e["name"], e["site_id"]))
    for m, cert in ((MEMBER_U1, 1), (MEMBER_U2, 0), (MEMBER_UD, 0)):
        cur.execute("INSERT INTO members VALUES (?,?,?,?,?)",
                    (m["id"], m["name"], m["enterprise_id"], cert,
                     "2020-01-01T00:00:00" if m["deleted"] else None))

    today = dt.date.today()
    cur_month = lambda day: now_month_day(today.replace(day=min(day, 28)))
    last_month = lambda: now_month_day(today - dt.timedelta(days=35))

    def inter(member, itype, when, activity=None, escalated=0):
        cur.execute(
            "INSERT INTO interactions(member_id,type,source,activity_id,escalated,occurred_at) "
            "VALUES (?,?,?,?,?,?)",
            (member["id"], itype, "mini", activity, escalated, when))

    # --- 会员 U1（企业 A）：全部有效互动，source=mini ---
    inter(MEMBER_U1, "auth", cur_month(2))                     # 认证 1
    inter(MEMBER_U1, "demand", cur_month(3))                   # 需求 1
    inter(MEMBER_U1, "signup", cur_month(4), ACTIVITY_1["id"])  # 报名 2 场
    inter(MEMBER_U1, "signup", cur_month(5), ACTIVITY_2["id"])
    inter(MEMBER_U1, "checkin", cur_month(6), ACTIVITY_1["id"]) # 签到 1（重复签到被唯一索引去重）
    try:
        inter(MEMBER_U1, "checkin", cur_month(6), ACTIVITY_1["id"])
    except sqlite3.IntegrityError:
        pass  # 重复签到去重：同活动同会员只计 1 次
    inter(MEMBER_U1, "ask", cur_month(7), escalated=0)          # 提问 3（其中 1 转人工）
    inter(MEMBER_U1, "ask", cur_month(8), escalated=0)
    inter(MEMBER_U1, "ask", cur_month(9), escalated=1)

    # --- 边界数据：不计入期望值 ---
    inter(MEMBER_U1, "browse", cur_month(10))                   # 纯浏览 ≠ 有效互动
    inter(MEMBER_U1, "demand", last_month())                    # 跨月互动不计当月
    inter(MEMBER_UD, "auth", cur_month(11))                     # 软删除会员不计
    inter(MEMBER_U2, "browse", cur_month(12))                   # 对照企业只浏览

    conn.commit()
    conn.close()
    print(f"loop4 场景已写入 {DB_PATH}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=["loop4"])
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()
    if a.scenario == "loop4":
        seed_scenario_loop4()
    elif a.reset:
        reset().close()
        print(f"已清库 {DB_PATH}")
    else:
        ap.print_help()
