#!/usr/bin/env python3
"""import_tags.py — intel_tags 种子导入（幂等）。

用法：
    python tools/import_tags.py --seed seed/intel_tags.yaml --db intel.db

以 (dimension, code) 为唯一键做 upsert；重复执行计数不变。
--emit-sql 可输出 PostgreSQL 版 INSERT ... ON CONFLICT 语句（对接正式 intel_tags 表）。
"""
from __future__ import annotations
import argparse, os, sqlite3, sys

import yaml

DDL = """
CREATE TABLE IF NOT EXISTS intel_tags (
    dimension     TEXT NOT NULL,
    code          TEXT NOT NULL,
    name          TEXT NOT NULL,
    definition    TEXT NOT NULL,
    positives     TEXT NOT NULL,
    negative      TEXT NOT NULL,
    crm_tag_code  TEXT,
    PRIMARY KEY (dimension, code)
);
"""


def load_seed(path: str) -> dict[str, list[dict]]:
    data = yaml.safe_load(open(path, encoding="utf-8"))
    expected_dims = {"policy_type", "industry", "region", "qualification", "company_size"}
    missing = expected_dims - set(data)
    if missing:
        raise ValueError(f"种子缺少维度: {sorted(missing)}")
    codes = []
    for dim, tags in data.items():
        for t in tags:
            codes.append((dim, t["code"]))
    if len(codes) != len(set(codes)):
        raise ValueError("种子内存在重复 (dimension, code)")
    return data


def _as_str(v):
    if isinstance(v, list):
        return " | ".join(str(x) for x in v)
    return v or ""


def upsert_sql(dim: str, t: dict) -> tuple:
    positives = _as_str(t.get("positives"))
    negative = _as_str(t.get("negative"))
    crm = t.get("crm_tag_code")
    return (
        "INSERT INTO intel_tags (dimension, code, name, definition, positives, negative, crm_tag_code) "
        "VALUES (?,?,?,?,?,?,?) "
        "ON CONFLICT(dimension, code) DO UPDATE SET name=excluded.name, definition=excluded.definition, "
        "positives=excluded.positives, negative=excluded.negative, crm_tag_code=excluded.crm_tag_code",
        (dim, t["code"], t["name"], t["definition"], positives, negative, crm),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", required=True)
    ap.add_argument("--db", default="intel.db")
    ap.add_argument("--emit-sql", action="store_true", help="输出 PG 版 SQL 而不落库")
    args = ap.parse_args()

    data = load_seed(args.seed)

    if args.emit_sql:
        for dim, tags in data.items():
            for t in tags:
                sql, params = upsert_sql(dim, t)
                ph = ", ".join(["?"] * 7)
                pg = sql.replace("?", "%s").replace("ON CONFLICT(dimension, code)", "ON CONFLICT (dimension, code)")
                print(f"{pg}; -- {tuple(params)}")
        return 0

    if os.path.exists(args.db):
        os.remove(args.db)
    con = sqlite3.connect(args.db)
    con.execute(DDL)
    n = 0
    for dim, tags in data.items():
        for t in tags:
            sql, params = upsert_sql(dim, t)
            con.execute(sql, params)
            n += 1
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM intel_tags").fetchone()[0]
    per = dict(con.execute("SELECT dimension, COUNT(*) FROM intel_tags GROUP BY dimension").fetchall())
    print(f"inserted={n} total_after={total} per_dim={per}")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
