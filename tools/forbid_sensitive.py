"""敏感字段扫描：按词根扫描列名，任何命中即失败（退出码 2）。

覆盖：name / uscc / mobile / phone / tel / id_card / idcard / email / address /
contact / wechat / passport / bank_account / real_name。
"""
from __future__ import annotations

import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, inspect  # noqa: E402

from app.calib.models import Base  # noqa: E402

FORBIDDEN_ROOTS = [
    "name", "uscc", "credit_code", "mobile", "phone", "tel", "id_card", "idcard",
    "email", "address", "contact", "wechat", "passport", "bank_account", "real_name",
]
# 允许的例外：不含真实标识的派生列
ALLOWED = {"company_pid"}


def main() -> int:
    schema = os.environ.get("CALIB_SCHEMA", "calib")
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    cols = [c["name"] for c in inspect(engine).get_columns("health_snapshot", schema=schema or None)]

    hits = []
    for col in cols:
        if col in ALLOWED:
            continue
        low = col.lower()
        for root in FORBIDDEN_ROOTS:
            if re.search(rf"(^|_){re.escape(root)}(_|$)", low):
                hits.append((col, root))
                break

    print(f"扫描 {schema}.health_snapshot 共 {len(cols)} 列")
    print("命中:", hits or "0 命中")
    print("RESULT", "OK" if not hits else "FAIL")
    return 0 if not hits else 2


if __name__ == "__main__":
    raise SystemExit(main())
