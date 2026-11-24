"""自检脚本：跑两遍汇总，输出 CSV 与幂等性哈希证据。

运行：python verify.py
产出：evidence/pages.csv、evidence/funnels.csv、evidence/verify.json
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.analytics.models import Base  # noqa: E402
from app.analytics.pipeline import read_funnel_stats, read_page_stats, run_day  # noqa: E402

DAY = dt.date(2026, 12, 1)
SITE = "11111111-1111-1111-1111-111111111111"
ORG = "22222222-2222-2222-2222-222222222222"


def dump(rows) -> str:
    return "\n".join(",".join(str(c) for c in r) for r in rows)


def main() -> int:
    out = ROOT / "evidence"
    out.mkdir(exist_ok=True)
    events = json.loads((ROOT / "fixtures" / "events.json").read_text(encoding="utf-8"))
    db = out / "verify.sqlite"
    if db.exists():
        db.unlink()
    engine = create_engine(f"sqlite+pysqlite:///{db}")

    import uuid
    with Session(engine) as s:
        Base.metadata.create_all(engine)
        stats1 = run_day(s, events, DAY, uuid.UUID(SITE), uuid.UUID(ORG))
        pages1, funnels1 = dump(read_page_stats(s)), dump(read_funnel_stats(s))
        s.commit()
    with Session(engine) as s:
        stats2 = run_day(s, events, DAY, uuid.UUID(SITE), uuid.UUID(ORG))
        pages2, funnels2 = dump(read_page_stats(s)), dump(read_funnel_stats(s))
        s.commit()

    (out / "pages.csv").write_text(
        "stat_date,page,pv,uv\n" + pages1, encoding="utf-8")
    (out / "funnels.csv").write_text(
        "funnel_code,scope_key,step_key,user_count\n" + funnels1, encoding="utf-8")

    sha = lambda text: hashlib.sha256(text.encode("utf-8")).hexdigest()  # noqa: E731
    result = {
        "rows": stats1,
        "page_rows_steady": pages1 == pages2,
        "funnel_rows_steady": funnels1 == funnels2,
        "pages_sha256_run1": sha(pages1),
        "pages_sha256_run2": sha(pages2),
        "funnels_sha256_run1": sha(funnels1),
        "funnels_sha256_run2": sha(funnels2),
        "page_count": len(pages1.splitlines()),
        "funnel_count": len(funnels1.splitlines()),
    }
    (out / "verify.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))
    ok = stats1["page_rows"] > 0 and result["page_rows_steady"] and result["funnel_rows_steady"]
    print("VERIFY", "OK" if ok else "FAIL")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
