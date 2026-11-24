import datetime as dt
import importlib
import pathlib
import sys

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import os
os.environ.setdefault("CALIB_SCHEMA", "")  # 测试库为 SQLite，无 schema

models = importlib.import_module("app.calib.models")
importlib.reload(models)
from app.calib.models import Base, HealthSnapshot, validate_row  # noqa: E402
import build_snapshot as bs  # noqa: E402

DAY = dt.date(2026, 12, 1)
RAW = {
    "uscc": "91310000MA1FL0XX0Y",
    "industry_code": "I65",
    "stage": "active",
    "membership_level": "vip",
    "tenure_days": 400,
    "days_to_expiry": 120,
    "event_raw": 6,
    "interaction_raw": 20,
    "resource_raw": 30,
    "opportunity_raw": 4,
    "space_raw": 60,
}


@pytest.fixture()
def engine():
    eng = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s


def test_migration_creates_table_with_expected_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("health_snapshot")}
    for name in models.BUSINESS_FIELDS + models.SYSTEM_FIELDS:
        assert name in cols, name
    assert len(cols) == 22


def test_dictionary_covers_all_columns(engine):
    from dictionary import fields as df
    cols = {c["name"] for c in inspect(engine).get_columns("health_snapshot")}
    assert cols == set(df.FIELDS)
    assert len([n for n in df.FIELDS if df.FIELDS[n].group in ("维度", "原始值", "标准化分")]) == 18
    for spec in df.FIELDS.values():
        assert spec.definition and spec.source and spec.range


def test_no_sensitive_columns(engine):
    cols = [c["name"] for c in inspect(engine).get_columns("health_snapshot")]
    for banned in ("name", "uscc", "mobile", "phone", "email", "address", "id_card"):
        assert banned not in cols
    assert "company_pid" in cols


def test_build_row_pseudonymizes_and_scores():
    row = bs.build_row(RAW, DAY, "SITE-A")
    assert row["company_pid"] == bs.pid(RAW["uscc"])
    assert len(row["company_pid"]) == 32 and RAW["uscc"] not in row["company_pid"]
    assert row["event_score"] == 50.0      # 6 / 12
    assert row["health_score"] is not None and 0 <= float(row["health_score"]) <= 100
    assert row["health_level"] in ("A", "B", "C", "D")


def test_missing_subitem_makes_total_null():
    raw = dict(RAW, space_raw=None)
    row = bs.build_row(raw, DAY, "SITE-A")
    assert row["space_score"] is None
    assert row["health_score"] is None and row["health_level"] is None


def test_tenure_zero_no_division_error():
    assert bs.tenure_rate(10, 0) is None
    assert bs.tenure_rate(None, 10) is None
    assert bs.tenure_rate(10, 30) == 10.0


def test_validation_rejects_non_first_day():
    row = bs.build_row(RAW, dt.date(2026, 12, 2), "SITE-A")
    assert any("每月 1 日" in e for e in validate_row(row))


def test_validation_rejects_bad_industry_code():
    for bad in ("i65", "I6", "I655"):
        row = bs.build_row(dict(RAW, industry_code=bad), DAY, "SITE-A")
        assert validate_row(row), bad


def test_health_score_range_check(session):
    row = bs.build_row(RAW, DAY, "SITE-A")
    row["health_score"] = 101
    session.add(HealthSnapshot(**row))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_health_level_enum_check(session):
    row = bs.build_row(RAW, DAY, "SITE-A")
    row["health_level"] = "Z"
    session.add(HealthSnapshot(**row))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_duplicate_snapshot_conflict(session):
    row = bs.build_row(RAW, DAY, "SITE-A")
    session.add(HealthSnapshot(**row))
    session.flush()
    session.add(HealthSnapshot(**row))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_upsert_is_idempotent(session):
    row = bs.build_row(RAW, DAY, "SITE-A")
    first = bs.upsert(session, [row])
    second = bs.upsert(session, [row])
    assert first["inserted"] == 1 and second["inserted"] == 0
    total = session.query(HealthSnapshot).count()
    assert total == 1


def test_upsert_collects_validation_errors(session):
    bad = bs.build_row(dict(RAW, industry_code="X"), DAY, "SITE-A")
    result = bs.upsert(session, [bad, bs.build_row(RAW, DAY, "SITE-A")])
    assert result["inserted"] == 1 and result["errors"]
