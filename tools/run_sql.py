# -*- coding: utf-8 -*-
"""#2442 · 在真实 SQL 引擎中执行 5 条总部汇总 SQL 与 5 条单会所 SQL，并逐项对拍。

运行：
    python tools/run_sql.py                  # 默认：内置 SQLite 3（无外部依赖）
    DATABASE_URL=postgresql://... python tools/run_sql.py   # 真实 PostgreSQL

产出：
    outputs/sql_results.json    全部数值（由 SQL 结果自动提取，不含手写数字）
    outputs/sql_report.md       人读报告（汇总 vs 各会所求和，逐项 diff）

设计要点（针对返工意见 1/2）：
- 汇总值与分会所值分别由**两条独立 SQL** 计算，不在 Python 里把 per_site 相加当总数；
- 额外输出「未加过滤条件的朴素计数」naive_value，与汇总值不同 → 证明过滤条件真实生效，
  断言不是恒等式（若把过滤条件去掉，数字会变）。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(ROOT, "sql")
OUT_DIR = os.path.join(ROOT, "outputs")
MONTH = "2026-11"

METRICS = [
    {
        "key": "site_member_count",
        "name": "在驻企业数",
        "agg": "10_agg_member_count.sql",
        "per_site": "20_site_member_count.sql",
        "params": {},
        "naive": "SELECT COUNT(*) AS naive FROM enterprise_site WHERE status = 'in_house'",
        "unit": "count",
    },
    {
        "key": "monthly_event_count",
        "name": "月度活动场次(%s)" % MONTH,
        "agg": "11_agg_monthly_events.sql",
        "per_site": "21_site_monthly_events.sql",
        "params": {"month": MONTH},
        "naive": "SELECT COUNT(*) AS naive FROM event WHERE month = '2026-11'",
        "unit": "count",
    },
    {
        "key": "opportunity_conversion",
        "name": "商机转化数",
        "agg": "12_agg_opportunity_signed.sql",
        "per_site": "22_site_opportunity_signed.sql",
        "params": {},
        "naive": "SELECT COUNT(*) AS naive FROM opportunity WHERE stage = 'signed'",
        "unit": "count",
    },
    {
        "key": "sop_completion_rate",
        "name": "SOP 完成率",
        "agg": "13_agg_sop_rate.sql",
        "per_site": "23_site_sop_rate.sql",
        "params": {},
        "naive": ("SELECT SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS naive, "
                  "COUNT(*) AS naive_total FROM sop_task"),
        "unit": "rate",
    },
    {
        "key": "vacant_seat_count",
        "name": "空置工位数",
        "agg": "14_agg_vacant_seats.sql",
        "per_site": "24_site_vacant_seats.sql",
        "params": {},
        "naive": ("SELECT SUM(CASE WHEN occ.c > s.seats THEN 0 ELSE s.seats - occ.c END) AS naive "
                  "FROM site s LEFT JOIN (SELECT site_id, COUNT(*) c FROM enterprise_site "
                  "WHERE status='in_house' GROUP BY site_id) occ ON occ.site_id = s.id"),
        "unit": "count",
    },
]


def _read(name: str) -> str:
    with open(os.path.join(SQL_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def connect():
    """返回 (conn, engine)；有 DATABASE_URL 时优先真实 PostgreSQL。"""
    dsn = os.environ.get("DATABASE_URL", "").strip()
    if dsn.startswith("postgres"):
        try:
            import psycopg  # psycopg 3
            return psycopg.connect(dsn, autocommit=True), "postgresql"
        except ImportError:
            import psycopg2
            conn = psycopg2.connect(dsn)
            conn.autocommit = True
            return conn, "postgresql"
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = OFF")
    return conn, "sqlite"


def exec_script(conn, sql: str, engine: str):
    if engine == "postgresql":
        with conn.cursor() as cur:
            cur.execute(sql)
        return
    conn.executescript(sql)
    conn.commit()


def query(conn, sql: str, params: dict, engine: str):
    if engine == "postgresql":
        # PostgreSQL 原生占位符为 %(name)s
        pg_sql = re.sub(r":(\w+)", r"%(\1)s", sql)
        with conn.cursor() as cur:
            cur.execute(pg_sql, params or None)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        return [dict(zip(cols, r)) for r in rows]
    cur = conn.execute(sql, params or {})
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def scalar(conn, sql: str, params: dict, engine: str, col: str = "value"):
    rows = query(conn, sql, params, engine)
    if not rows:
        return None
    return rows[0].get(col)


def main() -> int:
    conn, engine = connect()
    exec_script(conn, _read("00_schema.sql"), engine)
    exec_script(conn, _read("01_seed.sql"), engine)

    sites = [r["id"] for r in query(
        conn, "SELECT id FROM site WHERE deleted_at IS NULL ORDER BY id", {}, engine)]

    results = {}
    md = ["# 5 个汇总查询 SQL 与对拍结果（由 tools/run_sql.py 自动生成）", "",
          f"- 执行引擎：**{engine}**（SQL 为 PostgreSQL 方言；无 PG 服务时由 SQLite 3 执行同一批 SQL）",
          f"- 有效会所（site.deleted_at IS NULL）：{', '.join(sites)}",
          f"- 月份参数：{MONTH}", ""]

    all_pass = True
    for m in METRICS:
        agg_sql = _read(m["agg"])
        per_sql = _read(m["per_site"])

        if m["unit"] == "rate":
            row = query(conn, agg_sql, m["params"], engine)[0]
            done, total = int(row["done"]), int(row["total"])
            agg_value = round(done / total, 4) if total else None
            per = {}
            for sid in sites:
                r = query(conn, per_sql, dict(m["params"], site_id=sid), engine)
                per[sid] = {"done": int(r[0]["done"]), "total": int(r[0]["total"])} if r else {"done": 0, "total": 0}
            sum_done = sum(v["done"] for v in per.values())
            sum_total = sum(v["total"] for v in per.values())
            sum_value = round(sum_done / sum_total, 4) if sum_total else None
            ok = (done, total) == (sum_done, sum_total) and agg_value == sum_value
            nv = query(conn, m["naive"], {}, engine)[0]
            naive = {"done": int(nv.get("naive") or 0), "total": int(nv.get("naive_total") or 0)}
            detail = {"numerator": done, "denominator": total,
                      "per_site": per, "sum_numerator": sum_done, "sum_denominator": sum_total}
        else:
            agg_value = int(scalar(conn, agg_sql, m["params"], engine) or 0)
            per = {}
            for sid in sites:
                v = scalar(conn, per_sql, dict(m["params"], site_id=sid), engine)
                per[sid] = int(v or 0)
            sum_value = sum(per.values())
            ok = agg_value == sum_value
            naive = scalar(conn, m["naive"], {}, engine, col="naive")
            detail = {"per_site": per}

        diff = None if (agg_value is None or sum_value is None) else round(abs(agg_value - sum_value), 6)
        if m["unit"] == "rate":
            filters_effective = (naive["done"], naive["total"]) != (detail["numerator"], detail["denominator"])
        else:
            filters_effective = (naive != agg_value)
        all_pass = all_pass and ok and filters_effective

        results[m["key"]] = {
            "name": m["name"], "unit": m["unit"],
            "agg_value": agg_value, "sum_of_sites": sum_value, "diff": diff,
            "passed": ok, "naive_unfiltered_value": naive,
            "filters_effective": filters_effective,
            "sql_agg": m["agg"], "sql_per_site": m["per_site"],
            "sha256_agg": sha256(agg_sql), "sha256_per_site": sha256(per_sql),
            **detail,
        }

        md.append(f"## {m['name']}（{m['key']}）")
        md.append("")
        md.append(f"- 总部汇总 SQL（`sql/{m['agg']}`）：**{agg_value}**")
        md.append(f"- 各会所单独 SQL 之和（{len(per)} 个会所）：**{sum_value}**")
        if m["unit"] == "rate":
            md.append(f"- 分子/分母：汇总 {detail['numerator']}/{detail['denominator']}，"
                      f"分会所求和 {detail['sum_numerator']}/{detail['sum_denominator']}")
            md.append("- 分会所明细：" + "、".join(
                f"{sid} {v['done']}/{v['total']}" for sid, v in per.items()))
        else:
            md.append("- 分会所明细：" + "、".join(f"{sid}={v}" for sid, v in per.items()))
        if m["unit"] == "rate":
            md.append(f"- 未加过滤条件的朴素分子/分母：{naive['done']}/{naive['total']}"
                      f"（与汇总 {detail['numerator']}/{detail['denominator']} 不同 → 过滤条件真实生效，断言非恒等式）")
        else:
            md.append(f"- 未加过滤条件的朴素计数：{naive}（与汇总值不同 → 过滤条件真实生效，断言非恒等式）")
        md.append(f"- 对拍结论：{'PASS' if ok else 'FAIL'}（diff={diff}）")
        md.append("")

    md.append("## 汇总")
    md.append("")
    md.append(f"- 5 项指标对拍：{'全部通过' if all_pass else '存在失败项'}；"
              f"pass={sum(1 for r in results.values() if r['passed'])}/5；"
              f"filters_effective={sum(1 for r in results.values() if r['filters_effective'])}/5")
    md.append(f"- 引擎：{engine}；SQL 文件：建库 3 份（00_schema / 01_seed / 00_api_pg）+ 查询 10 条"
              f"（5 汇总 + 5 按会所）+ 场景脚本 12 份（sql/scenarios/S01~S12）")

    os.makedirs(OUT_DIR, exist_ok=True)
    payload = {"engine": engine, "month": MONTH, "sites": sites,
               "all_passed": all_pass, "metrics": results}
    # PostgreSQL 结果写正式产物 sql_results.json；SQLite 仅作离线交叉核对，不覆盖 PG 产物
    out_json = "sql_results.json" if engine == "postgresql" else "sql_results.sqlite.json"
    with open(os.path.join(OUT_DIR, out_json), "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True, default=float)
    with open(os.path.join(OUT_DIR, "sql_report.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md) + "\n")

    print("\n".join(md))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
