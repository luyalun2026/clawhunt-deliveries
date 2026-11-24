# -*- coding: utf-8 -*-
"""#2442 · 12 场景执行器（PostgreSQL 16）

设计原则（针对返工意见 1）：
- 12 个场景**不再跑内存模型**。每个场景就是一份 sql/scenarios/Sxx.sql 脚本，
  脚本内容是对 sql/00_schema.sql 建出的测试库执行**真实 SQL 或接口桩调用**；
- 脚本最后一行把「期望 / 实际 / 是否通过」写进 scenario_result 表，
  Python 侧只负责「跑脚本 + 从库里读回那一行」，**不参与计算、不拼数字**；
- 每个场景跑在同一连接的一个事务里，读完立即 ROLLBACK，场景之间互不污染。

用法：
    DATABASE_URL=postgresql://user:pass@127.0.0.1:5432/db python tools/run_matrix.py
"""
from __future__ import annotations

import glob
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(ROOT, "sql")
SCEN_DIR = os.path.join(SQL_DIR, "scenarios")

SCENARIOS = ["S01", "S02", "S03", "S04", "S05", "S06",
             "S07", "S08", "S09", "S10", "S11", "S12"]

NAMES = {
    "S01": "同一会员企业同时入驻两个会所",
    "S02": "会员在 B 会所报名 A 会所公开活动",
    "S03": "联系人跨会所更换负责人",
    "S04": "会所停业后历史数据只读",
    "S05": "商机从 A 会所转介到 B 会所",
    "S06": "知识库「机构共享」文章",
    "S07": "知识库「会所私有」文章",
    "S08": "机构级字典（空间类型）",
    "S09": "会所级配置（价格规则）",
    "S10": "总部跨会所汇总",
    "S11": "软删除语义",
    "S12": "数据导出范围",
}


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def dsn() -> str:
    v = os.environ.get("DATABASE_URL", "").strip()
    if not v.startswith("postgres"):
        raise SystemExit("DATABASE_URL 必须是 postgresql:// 连接串（本单约定 PostgreSQL 16）")
    return v


def connect():
    import psycopg
    return psycopg.connect(dsn(), autocommit=False)


def init_db(conn) -> None:
    """建库：表结构 → 种子数据 → 接口桩函数。"""
    with conn.cursor() as cur:
        cur.execute(read(os.path.join(SQL_DIR, "00_schema.sql")))
        cur.execute(read(os.path.join(SQL_DIR, "01_seed.sql")))
        cur.execute(read(os.path.join(SQL_DIR, "00_api_pg.sql")))
    conn.commit()


def run_scenario(conn, sid: str) -> dict:
    """执行一个场景脚本并读回它写进 scenario_result 的那一行；读完回滚。"""
    path = os.path.join(SCEN_DIR, sid + ".sql")
    sql = read(path)
    row = None
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute("SELECT expected, actual, ok FROM scenario_result WHERE scenario = %s", (sid,))
            row = cur.fetchone()
    finally:
        conn.rollback()
    if row is None:
        return {"id": sid, "name": NAMES[sid], "expected": "", "actual": "脚本未写入 scenario_result",
                "ok": False, "script": os.path.relpath(path, ROOT).replace("\\", "/"),
                "sha256": sha256(sql), "error": "no_result_row"}
    return {"id": sid, "name": NAMES[sid], "expected": row[0], "actual": row[1], "ok": bool(row[2]),
            "script": os.path.relpath(path, ROOT).replace("\\", "/"),
            "sha256": sha256(sql)}


def run_all(conn) -> list[dict]:
    return [run_scenario(conn, sid) for sid in SCENARIOS]


def scenario_files() -> list[str]:
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(SCEN_DIR, "S*.sql")))


if __name__ == "__main__":
    c = connect()
    init_db(c)
    for r in run_all(c):
        print("%s %s %s" % ("PASS" if r["ok"] else "FAIL", r["id"], r["actual"]))
    c.close()
    sys.exit(0)
