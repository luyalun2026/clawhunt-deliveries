"""生成月度快照：假名化 → 标准化 → 汇总 → 校验 → 写库。

唯一写入口：各校准脚本只读 calib.health_snapshot。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import os
import sys
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.calib.models import Base, HealthSnapshot, validate_row  # noqa: E402

PEPPER = os.environ.get("CALIB_PEPPER", "calib-dev-pepper-2026").encode()
ALGO_VERSION = "v1"

WEIGHTS = {
    "event_score": Decimal("0.20"),
    "interaction_score": Decimal("0.25"),
    "resource_score": Decimal("0.20"),
    "opportunity_score": Decimal("0.20"),
    "space_score": Decimal("0.15"),
}

# normalize 的 p10/p95 标定值（与生产健康分同一口径，来自历史分布）
CALIB = {
    "event_raw": (0, 12),
    "interaction_raw": (0, 40),
    "resource_raw": (0, 60),
    "opportunity_raw": (0, 8),
    "space_raw": (0, 120),
}


def pid(uscc: str) -> str:
    """企业假名 ID：HMAC-SHA256 取前 32 位十六进制，不可逆。"""
    return hmac.new(PEPPER, uscc.strip().upper().encode(), hashlib.sha256).hexdigest()[:32]


def normalize(value, p10: float, p95: float) -> Decimal | None:
    """与生产健康分同一套线性截断标准化，输出 0–100。"""
    if value is None:
        return None
    span = float(p95) - float(p10)
    if span <= 0:
        return None
    ratio = (float(value) - float(p10)) / span
    ratio = min(1.0, max(0.0, ratio))
    return Decimal(str(round(ratio * 100, 2)))


def level_of(score: Decimal | None) -> str | None:
    if score is None:
        return None
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    return "D"


def tenure_rate(value: int | None, tenure_days: int) -> Decimal | None:
    """按入会天数折算的月均次数；tenure_days=0 时返回 None（不做除零）。"""
    if value is None or tenure_days <= 0:
        return None
    return (Decimal(value) / Decimal(tenure_days) * Decimal(30)).quantize(Decimal("0.01"))


def build_row(raw: dict, snapshot_date: dt.date, site_code: str) -> dict:
    """raw 为业务侧脱敏导出的一行（无 name/uscc/mobile）。"""
    row: dict = {
        "snapshot_date": snapshot_date,
        "company_pid": pid(raw["uscc"]),
        "site_code": site_code,
        "industry_code": raw["industry_code"],
        "stage": raw["stage"],
        "membership_level": raw["membership_level"],
        "tenure_days": int(raw["tenure_days"]),
        "days_to_expiry": int(raw["days_to_expiry"]),
        "algorithm_version": ALGO_VERSION,
    }
    score_map = {
        "event_raw": "event_score",
        "interaction_raw": "interaction_score",
        "resource_raw": "resource_score",
        "opportunity_raw": "opportunity_score",
        "space_raw": "space_score",
    }
    for raw_key, score_key in score_map.items():
        value = raw.get(raw_key)
        row[raw_key] = value
        p10, p95 = CALIB[raw_key]
        row[score_key] = normalize(value, p10, p95)

    if all(row[k] is not None for k in score_map.values()):
        total = sum(row[k] * w for k, w in WEIGHTS.items())
        row["health_score"] = Decimal(total).quantize(Decimal("0.01"))
        row["health_level"] = level_of(row["health_score"])
    else:
        # 任一子项缺失：总分与等级一律 NULL，不按 0 补齐
        row["health_score"] = None
        row["health_level"] = None
    return row


def upsert(session: Session, rows: list[dict]) -> dict:
    errors: list[str] = []
    inserted = 0
    for row in rows:
        problems = validate_row(row)
        if problems:
            errors.append(f"{row.get('company_pid')}: {'; '.join(problems)}")
            continue
        exists = session.get(HealthSnapshot, (row["snapshot_date"], row["company_pid"]))
        if exists:
            for key, value in row.items():
                setattr(exists, key, value)
        else:
            session.add(HealthSnapshot(**row))
            inserted += 1
    session.flush()
    return {"inserted": inserted, "errors": errors}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().replace(day=1).isoformat())
    ap.add_argument("--db", default=os.environ.get("DATABASE_URL", "sqlite+pysqlite:///:memory:"))
    args = ap.parse_args()
    snapshot_date = dt.date.fromisoformat(args.date)
    engine = create_engine(args.db)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        print(f"snapshot_date={snapshot_date} schema={HealthSnapshot.__table__.schema}")
        s.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
