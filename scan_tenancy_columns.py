# -*- coding: utf-8 -*-
"""#2430 多会所字段覆盖扫描：org_id / site_id 与索引核查。

用法：
  DATABASE_URL=postgresql://... python scan_tenancy_columns.py \
      --rules tenancy_rules.yaml --schema public \
      --report-md outputs/report.md --report-json outputs/report.json

* 数据来源：information_schema.columns / pg_indexes / 约束目录（零手写数字）。
* 分类：tenancy_rules.yaml（会所级 site / 机构级共享 org / 全局字典 global）。
* 未登记表 → blocker，退出码 1（AC3）。
* 存在 blocker 时退出码 1，可接入 CI。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

BLOCKER = "blocker"
MAJOR = "major"
WARN = "warn"

from sqlalchemy import text as _text

SQL_TABLES = _text("""
SELECT table_name FROM information_schema.tables
WHERE table_schema = :schema AND table_type = 'BASE TABLE'
""")
SQL_COLUMNS = _text("""
SELECT table_name, column_name, is_nullable
FROM information_schema.columns
WHERE table_schema = :schema
ORDER BY table_name, ordinal_position
""")
SQL_INDEXES = _text("""
SELECT tablename, indexname, indexdef FROM pg_indexes
WHERE schemaname = :schema
""")
SQL_FKS = _text("""
SELECT tc.table_name, kcu.column_name, ccu.table_name AS foreign_table
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = :schema
""")
# SQLite（测试路径）目录查询
SQLI_TABLES = _text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
SQLI_COLUMNS = _text("""
SELECT :tname AS table_name, name AS column_name,
       CASE WHEN "notnull" = 0 THEN 'YES' ELSE 'NO' END AS is_nullable
FROM pragma_table_info(:tname)
""")
SQLI_INDEXES = _text("SELECT name, COALESCE(sql, name) AS indexdef FROM sqlite_master WHERE type='index' AND tbl_name=:tname")


def _list_tables(conn, schema: str) -> list[str]:
    if conn.dialect.name == "sqlite":
        return [r[0] for r in conn.execute(SQLI_TABLES).fetchall()]
    return [r[0] for r in conn.execute(SQL_TABLES, {"schema": schema}).fetchall()]


def _catalog(conn, schema: str):
    """返回 (cols, idx, fks)。PG 走 information_schema/pg_indexes；SQLite 走 pragma。"""
    cols: dict[str, list] = {}
    idx: dict[str, list] = {}
    fks: dict[str, list] = {}
    if conn.dialect.name == "sqlite":
        tables = _list_tables(conn, schema)
        for t in tables:
            for tn, cn, nullable in conn.execute(SQLI_COLUMNS, {"tname": t}).fetchall():
                cols.setdefault(tn, []).append((cn, nullable))
            for _, idef in conn.execute(SQLI_INDEXES, {"tname": t}).fetchall():
                idx.setdefault(t, []).append(idef)
        # SQLite 外键：pragma foreign_key_list
        from sqlalchemy import text as t2
        for t in tables:
            for fk in conn.execute(t2(f"PRAGMA foreign_key_list({t})")).fetchall():
                fks.setdefault(t, []).append((fk[3], fk[2]))
    else:
        for tn, cn, nullable in conn.execute(SQL_COLUMNS, {"schema": schema}).fetchall():
            cols.setdefault(tn, []).append((cn, nullable))
        for tn, iname, idef in conn.execute(SQL_INDEXES, {"schema": schema}).fetchall():
            idx.setdefault(tn, []).append(idef)
        for tn, cn, ft in conn.execute(SQL_FKS, {"schema": schema}).fetchall():
            fks.setdefault(tn, []).append((cn, ft))
    return cols, idx, fks


def load_rules(path: Path) -> dict:
    if yaml is not None:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    # 极简 YAML 子集解析（tables.<name>: {class: ...}），保证无 PyYAML 也能跑测试
    rules: dict = {"tables": {}}
    current = None
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.startswith("tables:") :
            continue
        if line.startswith("  ") and ":" in line:
            key, _, val = line.strip().partition(":")
            if current is not None:
                rules["tables"].setdefault(current, {})[key.strip()] = val.strip().strip('"')
        elif not line.startswith(" ") and line.endswith(":"):
            pass
        else:
            current = line.split(":")[0].strip()
            rules["tables"].setdefault(current, {"class": "unregistered"})
    return rules


def scan(conn, schema: str, rules: dict) -> dict:
    tables = _list_tables(conn, schema)
    cols, idx, fks = _catalog(conn, schema)

    registered = rules.get("tables", {})
    rows = []
    n_blocker = n_major = n_warn = 0
    for t in tables:
        tcols = cols.get(t, [])
        colnames = {c for c, _ in tcols}
        entry = registered.get(t)
        if entry is None:
            rows.append({"table": t, "class": "unregistered", "missing_columns": [],
                         "missing_indexes": [], "cross_org_fk_risk": [], "level": BLOCKER})
            n_blocker += 1
            continue
        klass = entry.get("class", "org")
        missing_cols: list[str] = []
        if klass in ("site", "org") and "org_id" not in colnames:
            missing_cols.append("org_id")
        if klass == "site" and "site_id" not in colnames:
            missing_cols.append("site_id")
        missing_idx: list[str] = []
        idx_items = idx.get(t, [])
        has_org_idx = any("org_id" in str(i) for i in idx_items)
        need_org_idx = klass in ("site", "org") and "org_id" in colnames
        if need_org_idx and not has_org_idx:
            missing_idx.append("(org_id) 或 (org_id, site_id) 前缀索引")
        if klass == "site" and "site_id" in colnames and not any("site_id" in str(i) for i in idx_items):
            missing_idx.append("(site_id) 索引")
        cross_org = [(cn, ft) for cn, ft in fks.get(t, []) if ft in tables and ft not in registered]
        level = BLOCKER if ("site_id" in missing_cols and klass == "site") else (MAJOR if (missing_cols or missing_idx) else WARN if cross_org else "ok")
        if level == BLOCKER:
            n_blocker += 1
        elif level == MAJOR:
            n_major += 1
        elif level == WARN:
            n_warn += 1
        rows.append({"table": t, "class": klass, "missing_columns": missing_cols,
                     "missing_indexes": missing_idx, "cross_org_fk_risk": cross_org,
                     "level": level})
    return {"schema": schema, "business_table_count": len(tables),
            "tables": rows, "summary": {"blocker": n_blocker, "major": n_major, "warn": n_warn}}


def write_reports(result: dict, md_path: Path | None, json_path: Path | None) -> None:
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    if md_path:
        md_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# 多会所字段覆盖扫描报告（schema={result['schema']}）",
            "",
            f"业务表总数：{result['business_table_count']}（与 information_schema 统计一致）",
            f"级别统计：blocker={result['summary']['blocker']} major={result['summary']['major']} warn={result['summary']['warn']}",
            "",
            "| 表名 | 分类 | 缺失字段 | 缺失索引 | 跨 org 引用风险 | 问题级别 |",
            "|---|---|---|---|---|---|",
        ]
        for r in sorted(result["tables"], key=lambda x: x["level"] != BLOCKER):
            lines.append("| {table} | {cls} | {mc} | {mi} | {co} | {lv} |".format(
                table=r["table"], cls=r["class"],
                mc=", ".join(r["missing_columns"]) or "-",
                mi="; ".join(r["missing_indexes"]) or "-",
                co="; ".join(f"{c}->{f}" for c, f in r["cross_org_fk_risk"]) or "-",
                lv=r["level"]))
        md_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default="tenancy_rules.yaml")
    ap.add_argument("--schema", default="public")
    ap.add_argument("--report-md", default=None)
    ap.add_argument("--report-json", default=None)
    args = ap.parse_args(argv)
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL 环境变量未设置", file=sys.stderr)
        return 2
    from sqlalchemy import create_engine
    engine = create_engine(dsn)
    rules = load_rules(Path(args.rules))
    with engine.connect() as conn:
        result = scan(conn, args.schema, rules)
    write_reports(result, Path(args.report_md) if args.report_md else None,
                  Path(args.report_json) if args.report_json else None)
    print(f"tables={result['business_table_count']} blocker={result['summary']['blocker']}"
          f" major={result['summary']['major']} warn={result['summary']['warn']}")
    return 1 if result["summary"]["blocker"] else 0


if __name__ == "__main__":
    sys.exit(main())
