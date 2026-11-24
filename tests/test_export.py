import datetime as dt
import io
import pathlib
import sys

import pytest
from openpyxl import load_workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.finance.export_service import (  # noqa: E402
    FLAG_CHANGED, MissingMapping, cents_to_yuan, export, seed_mappings,
)
from app.finance.models import Base, ExportRun, PeriodLock  # noqa: E402

PERIOD = "2026-11"

RECEIVABLES = [
    dict(contract_no="HT-001", company="甲公司", fee_type="场地费", period=PERIOD,
         net_cents=40000, tax_cents=2400, gross_cents=42400),
    dict(contract_no="HT-002", company="甲公司", fee_type="服务费", period=PERIOD,
         net_cents=20000, tax_cents=1200, gross_cents=21200),
    dict(contract_no="HT-003", company="乙公司", fee_type="场地费", period=PERIOD,
         net_cents=300000, tax_cents=18000, gross_cents=318000),
    dict(contract_no="HT-004", company="乙公司", fee_type="服务费", period=PERIOD,
         net_cents=100000, tax_cents=6000, gross_cents=106000),
    dict(contract_no="HT-005", company="丙公司", fee_type="场地费", period=PERIOD,
         net_cents=500000, tax_cents=30000, gross_cents=530000),
    dict(contract_no="HT-006", company="丙公司", fee_type="服务费", period=PERIOD,
         net_cents=400000, tax_cents=22400, gross_cents=422400),
]
RECEIPTS = [
    dict(bank_serial="BX001", received_date="2026-11-05", company="甲公司",
         installment="2026-11 第1期", amount_cents=300000, period=PERIOD),
    dict(bank_serial="BX002", received_date="2026-11-10", company="乙公司",
         installment="2026-11 第1期", amount_cents=250000, period=PERIOD),
    dict(bank_serial="BX003", received_date="2026-11-18", company="乙公司",
         installment="2026-11 第2期", amount_cents=200000, period=PERIOD),
    dict(bank_serial="BX004", received_date="2026-11-28", company="丙公司",
         installment="2026-11 第1期", amount_cents=230000, period=PERIOD),
]
MAPPINGS = [("场地费", "6001.01", "1122.01", "2221.01"),
            ("服务费", "6001.02", "1122.02", "2221.02")]


@pytest.fixture()
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        seed_mappings(s, MAPPINGS)
        yield s


def test_receivable_totals_match_report(session):
    res = export(session, period=PERIOD, export_type="receivable", fmt="csv", data=RECEIVABLES)
    assert res["rows"] == 6
    assert sum(r["gross_cents"] for r in RECEIVABLES) == 1440000
    assert res["total_cents"] == 1440000
    for row in RECEIVABLES:
        assert row["net_cents"] + row["tax_cents"] == row["gross_cents"]
    text = res["payload"].decode("utf-8-sig")
    assert text.splitlines()[0].startswith("合同编号")
    assert "6001.01" in text and "1122.02" in text


def test_receipt_totals_match_report(session):
    res = export(session, period=PERIOD, export_type="receipt", fmt="csv", data=RECEIPTS)
    assert res["rows"] == 4
    assert res["total_cents"] == sum(r["amount_cents"] for r in RECEIPTS) == 980000


def test_yuan_column_equals_cents_over_100(session):
    res = export(session, period=PERIOD, export_type="receipt", fmt="csv", data=RECEIPTS)
    lines = res["payload"].decode("utf-8-sig").splitlines()[1:]
    for line, row in zip(lines, RECEIPTS):
        cells = line.split(",")
        assert cells[4] == str(row["amount_cents"])
        assert cells[5] == cents_to_yuan(row["amount_cents"])


def test_identity_violation_rejected(session):
    bad = [dict(RECEIVABLES[0], gross_cents=1)]
    with pytest.raises(ValueError) as exc:
        export(session, period=PERIOD, export_type="receivable", fmt="csv", data=bad)
    assert "恒等式" in str(exc.value)


def test_missing_mapping_fails_with_fee_types(session):
    data = RECEIVABLES + [dict(contract_no="HT-009", company="丁公司", fee_type="广告费",
                               period=PERIOD, net_cents=1000, tax_cents=60, gross_cents=1060)]
    with pytest.raises(MissingMapping) as exc:
        export(session, period=PERIOD, export_type="receivable", fmt="csv", data=data)
    assert exc.value.missing == ["广告费"]


def test_adjustment_generated_after_modification(session):
    export(session, period=PERIOD, export_type="receipt", fmt="csv", data=RECEIPTS)
    modified = [dict(r) for r in RECEIPTS]
    modified[0]["amount_cents"] = 290000          # 300000 → 290000，差额 -10000
    res = export(session, period=PERIOD, export_type="receipt", fmt="csv", data=modified)
    assert res["is_adjustment"] is True
    text = res["payload"].decode("utf-8-sig")
    assert FLAG_CHANGED in text
    adj_line = [l for l in text.splitlines() if FLAG_CHANGED in l][0].split(",")
    assert adj_line[4] == "-10000" and adj_line[7] == "300000" and adj_line[8] == "-10000"


def test_unmodified_second_export_matches_first(session):
    first = export(session, period=PERIOD, export_type="receipt", fmt="csv", data=RECEIPTS)
    second = export(session, period=PERIOD, export_type="receipt", fmt="csv", data=RECEIPTS)
    assert second["is_adjustment"] is True          # 期间已锁定
    assert second["payload"] == first["payload"]
    assert second["sha256"] == first["sha256"]


def test_audit_row_per_export(session):
    assert session.query(ExportRun).count() == 0
    for _ in range(3):
        export(session, period=PERIOD, export_type="receipt", fmt="csv", data=RECEIPTS)
    runs = session.execute(select(ExportRun)).scalars().all()
    assert len(runs) == 3
    assert all(r.period == PERIOD and r.row_count == 4 and r.file_sha256 for r in runs)


def test_period_lock_written_once(session):
    export(session, period=PERIOD, export_type="receipt", fmt="csv", data=RECEIPTS)
    first_at = session.get(PeriodLock, PERIOD).first_exported_at
    export(session, period=PERIOD, export_type="receipt", fmt="csv", data=RECEIPTS)
    locks = session.query(PeriodLock).all()
    assert len(locks) == 1 and locks[0].first_exported_at == first_at


def test_csv_has_bom(session):
    res = export(session, period=PERIOD, export_type="receipt", fmt="csv", data=RECEIPTS)
    assert res["payload"][:3] == b"\xef\xbb\xbf"


def test_xlsx_money_format_and_no_scientific(session):
    res = export(session, period=PERIOD, export_type="receivable", fmt="xlsx", data=RECEIVABLES)
    wb = load_workbook(io.BytesIO(res["payload"]))
    ws = wb.active
    assert ws.max_row == 7
    cell = ws.cell(row=2, column=5)      # 不含税金额(分)
    assert isinstance(cell.value, int)
    assert ws.cell(row=2, column=6).number_format == "#,##0.00"   # 元列两位小数
    assert ws.cell(row=2, column=5).number_format == "#,##0"        # 分列整数


def test_empty_period_rows(session):
    res = export(session, period="2026-10", export_type="receipt", fmt="csv", data=RECEIPTS)
    assert res["rows"] == 0 and res["total_cents"] == 0
    assert session.query(ExportRun).count() == 1


def test_zero_tax_row(session):
    data = [dict(RECEIVABLES[0], net_cents=100000, tax_cents=0, gross_cents=100000)]
    res = export(session, period=PERIOD, export_type="receivable", fmt="csv", data=data)
    assert res["total_cents"] == 100000


def test_cross_period_rows_excluded(session):
    other = dict(RECEIPTS[0], bank_serial="BX900", period="2026-10")
    res = export(session, period=PERIOD, export_type="receipt", fmt="csv",
                 data=RECEIPTS + [other])
    assert res["rows"] == 4
