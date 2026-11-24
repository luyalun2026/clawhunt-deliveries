import datetime as dt
import io
import pathlib
import sys
import time

import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.finance.importer import (  # noqa: E402
    import_rows, is_credit, map_row, parse_amount_cents, parse_date, read_csv, read_xlsx,
)
from app.finance.models import BankImportBatch, BankTransaction, Base  # noqa: E402

TEMPLATE_A = {
    "id": None, "bank_code": "BANK_A", "name": "虚构银行A",
    "columns": {
        "txn_date": "交易日期", "amount": "金额", "direction": "借贷标志",
        "counterparty_name": "对方户名", "counterparty_account": "对方账号",
        "memo": "摘要", "bank_serial": "流水号",
    },
    "date_formats": ["%Y-%m-%d", "%Y/%m/%d"],
}
TEMPLATE_B = {
    "id": None, "bank_code": "BANK_B", "name": "虚构银行B",
    "columns": {
        "txn_date": "记账日", "amount": "发生额", "direction": "收付方向",
        "counterparty_name": "对方名称", "counterparty_account": "对方账号",
        "memo": "附言", "bank_serial": "参考号",
    },
    "date_formats": ["%Y%m%d", "%Y-%m-%d"],
}

CSV_A = """交易日期,金额,借贷标志,对方户名,对方账号,摘要,流水号
2026-12-01,"1,234.56",贷,甲公司,6222001,会费,SN001
2026-12-01,0.01,贷,乙公司,6222002,补差,SN002
2026-12-02,(56.70),借,丙公司,6222003,退费,SN003
2026-12-02,88.00,借,丁公司,6222004,支出,SN004
2026-12-03,500.00,贷,甲公司,6222001,续费,SN005
2026-12-03,500.00,贷,甲公司,6222001,续费,SN005
2026-12-04,abc,贷,戊公司,6222005,脏数据,SN006
"""


@pytest.fixture()
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_parse_amount_cents_exact():
    assert parse_amount_cents("1,234.56") == 123456
    assert parse_amount_cents("0.01") == 1
    assert parse_amount_cents("(56.70)") == -5670
    assert parse_amount_cents("￥100.00") == 10000
    assert parse_amount_cents("-56.70") == -5670
    with pytest.raises(ValueError):
        parse_amount_cents("")


def test_direction_double_check():
    assert is_credit("贷", 100) == (True, None)
    assert is_credit("借", -100) == (False, None)
    assert is_credit("借", 100) == (False, None)      # 金额恒正的银行排版
    credit, conflict = is_credit("贷", -100)          # 贷方 + 负数是矛盾行
    assert credit is False and conflict
    credit, conflict = is_credit("X", 100)
    assert credit is False and conflict and "未知" in conflict


def test_template_a_import_amounts_and_counts(session):
    rows = read_csv(CSV_A.encode("utf-8"))
    batch = import_rows(session, rows, TEMPLATE_A, "ACC-A", filename="bank_a.csv")
    assert batch.added == 3           # SN001 / SN002 / SN005
    assert batch.skipped_debit == 2   # SN003 / SN004
    assert batch.skipped_dup == 1     # 重复的 SN005
    assert batch.failed == 1          # abc 脏行
    amounts = {t.bank_serial: t.amount_cents for t in session.execute(select(BankTransaction)).scalars()}
    assert amounts == {"SN001": 123456, "SN002": 1, "SN005": 50000}


def test_template_b_xlsx_import(session):
    wb = Workbook()
    ws = wb.active
    ws.append(["记账日", "发生额", "收付方向", "对方名称", "对方账号", "附言", "参考号"])
    ws.append([20261205, 1234.56, "收入", "己公司", "6222006", "服务费", "BX001"])
    ws.append(["2026-12-05", 0.10, "支出", "庚公司", "6222007", "退款", "BX002"])
    buf = io.BytesIO()
    wb.save(buf)
    rows = read_xlsx(buf.getvalue())
    batch = import_rows(session, rows, TEMPLATE_B, "ACC-B", filename="bank_b.xlsx")
    assert batch.added == 1 and batch.skipped_debit == 1 and batch.failed == 0
    txn = session.execute(select(BankTransaction)).scalar_one()
    assert txn.amount_cents == 123456 and txn.txn_date == dt.date(2026, 12, 5)


def test_duplicate_file_zero_new(session):
    rows = read_csv(CSV_A.encode("utf-8"))
    first = import_rows(session, rows, TEMPLATE_A, "ACC-A")
    second = import_rows(session, rows, TEMPLATE_A, "ACC-A")
    assert first.added == 3
    assert second.added == 0
    assert second.skipped_dup == 4     # 3 条库内已存在 + 1 条批内重复
    assert session.query(BankTransaction).count() == 3


def test_debit_never_persisted(session):
    rows = read_csv(CSV_A.encode("utf-8"))
    import_rows(session, rows, TEMPLATE_A, "ACC-A")
    serials = {t.bank_serial for t in session.execute(select(BankTransaction)).scalars()}
    assert "SN003" not in serials and "SN004" not in serials


def test_5000_rows_under_60s(session, tmp_path):
    header = "交易日期,金额,借贷标志,对方户名,对方账号,摘要,流水号\n"
    lines = [header]
    for i in range(5000):
        direction = "贷" if i % 10 else "借"      # 每 10 行 1 行借方
        lines.append(f"2026-12-01,{i + 1}.25,{direction},公司{i},6222{i:04d},批量,SN{i:06d}\n")
    rows = read_csv("".join(lines).encode("utf-8"))
    assert len(rows) == 5000
    started = time.perf_counter()
    batch = import_rows(session, rows, TEMPLATE_A, "ACC-PERF")
    elapsed = time.perf_counter() - started
    log = tmp_path / "timing.log"
    log.write_text(f"rows=5000 elapsed_ms={batch.elapsed_ms} wall_ms={int(elapsed * 1000)} "
                   f"added={batch.added} skipped_debit={batch.skipped_debit}\n", encoding="utf-8")
    assert batch.added == 4500 and batch.skipped_debit == 500
    assert elapsed < 60, f"{elapsed:.2f}s"
    print(log.read_text(encoding="utf-8"))


def test_row_level_errors_reported(session):
    rows = read_csv(("交易日期,金额,借贷标志,对方户名,对方账号,摘要,流水号\n"
                     "2026-12-01,abc,贷,A,1,x,SN900\n"
                     "2026-13-45,10.00,贷,B,2,x,SN901\n"
                     ",10.00,贷,C,3,x,SN902\n").encode("utf-8"))
    batch = import_rows(session, rows, TEMPLATE_A, "ACC-E")
    assert batch.added == 0 and batch.failed == 3
    rows_reported = sorted(e["row"] for e in batch.errors)
    assert rows_reported == [2, 3, 4]


def test_empty_and_header_only(session):
    assert import_rows(session, [], TEMPLATE_A, "ACC-E").total_rows == 0
    rows = read_csv("交易日期,金额,借贷标志,对方户名,对方账号,摘要,流水号\n".encode("utf-8"))
    batch = import_rows(session, rows, TEMPLATE_A, "ACC-E")
    assert batch.added == 0 and batch.status == "succeeded"


def test_over_limit_rejected(session):
    rows = [{"交易日期": "2026-12-01", "金额": "1.00", "借贷标志": "贷",
             "对方户名": "X", "对方账号": "1", "摘要": "", "流水号": f"S{i}"}
            for i in range(11)]
    batch = import_rows(session, rows, TEMPLATE_A, "ACC-X", max_rows=10)
    assert batch.status == "failed" and batch.added == 0


def test_date_formats(session):
    assert parse_date("2026/1/5", ["%Y/%m/%d", "%Y-%m-%d"]) == dt.date(2026, 1, 5)
    assert parse_date("20260105", ["%Y%m%d"]) == dt.date(2026, 1, 5)
    assert parse_date(dt.datetime(2026, 3, 4, 5, 6), ["%Y-%m-%d"]) == dt.date(2026, 3, 4)


def test_mapping_missing_serial_rejected(session):
    rows = [{"交易日期": "2026-12-01", "金额": "10.00", "借贷标志": "贷",
             "对方户名": "X", "对方账号": "1", "摘要": "", "流水号": ""}]
    batch = import_rows(session, rows, TEMPLATE_A, "ACC-M")
    assert batch.failed == 1 and "流水号" in batch.errors[0]["reason"]
