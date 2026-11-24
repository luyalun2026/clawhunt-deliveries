"""字典与数据库实际列的双向比对 + 字典渲染。

用法：
  python tools/check_dictionary.py            # 比对（退出码 0/2）
  python tools/check_dictionary.py --render   # 生成 dictionary.md / dictionary.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, inspect  # noqa: E402

from app.calib.models import Base, BUSINESS_FIELDS, SYSTEM_FIELDS  # noqa: E402
from dictionary import fields as dict_fields  # noqa: E402

TABLE = "health_snapshot"
SCHEMA = os.environ.get("CALIB_SCHEMA", "calib")


def actual_columns(engine) -> dict[str, dict]:
    insp = inspect(engine)
    cols = insp.get_columns(TABLE, schema=SCHEMA or None)
    return {c["name"]: c for c in cols}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--db", default="")
    args = ap.parse_args()

    if args.render:
        (ROOT / "dictionary.md").write_text(dict_fields.render_markdown(), encoding="utf-8")
        with (ROOT / "dictionary.csv").open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(dict_fields.as_dicts()[0].keys()))
            writer.writeheader()
            writer.writerows(dict_fields.as_dicts())
        print(f"rendered dictionary.md / dictionary.csv  fields={len(dict_fields.FIELDS)}")
        return 0

    db_url = args.db or "sqlite+pysqlite:///:memory:"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    actual = actual_columns(engine)
    documented = set(dict_fields.FIELDS)

    undocumented = sorted(set(actual) - documented)
    phantom = sorted(documented - set(actual))
    business_ok = [n for n in BUSINESS_FIELDS if n in actual and n in documented]
    system_ok = [n for n in SYSTEM_FIELDS if n in actual and n in documented]

    print(f"表 {SCHEMA}.{TABLE} 实际列 {len(actual)} 个，字典 {len(documented)} 个")
    print(f"业务字段匹配: {len(business_ok)}/{len(BUSINESS_FIELDS)}")
    print(f"系统字段匹配: {len(system_ok)}/{len(SYSTEM_FIELDS)}")
    print("缺文档的列:", undocumented or "无")
    print("文档多出的列:", phantom or "无")
    ok = not undocumented and not phantom and len(business_ok) == 18
    print("RESULT", "OK" if ok else "FAIL")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
