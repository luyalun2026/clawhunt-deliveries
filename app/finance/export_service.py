"""应收 / 实收凭证明细导出。

口径：
- 金额一律以「分」存整数，同时输出「元」列（分/100，两位小数），不使用 float 汇总。
- 应收行必须满足 不含税 + 税额 = 价税合计，否则拒绝导出并列出违例行。
- 首次导出写入 export_snapshots + period_locks；再次导出逐行比对快照，
  变更行输出「调整」行（原值/新值/差额）并标记「已导出期间变更」。
- 每次导出写 1 条 export_runs 审计。
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import uuid
from decimal import Decimal

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AccountingMapping, ExportRun, ExportSnapshot, PeriodLock

FLAG_CHANGED = "已导出期间变更"

RECEIVABLE_HEADER = ["合同编号", "企业名称", "费用类型", "所属期间", "不含税金额(分)", "不含税金额(元)",
                     "税额(分)", "税额(元)", "价税合计(分)", "价税合计(元)",
                     "收入科目", "应收科目", "税额科目", "标记", "原值(分)", "差额(分)"]
RECEIPT_HEADER = ["银行流水号", "到账日期", "企业名称", "核销分期", "核销金额(分)", "核销金额(元)",
                  "标记", "原值(分)", "差额(分)"]


class MissingMapping(Exception):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("科目映射缺失：" + "、".join(missing))


def cents_to_yuan(cents: int) -> str:
    return str((Decimal(cents) / Decimal(100)).quantize(Decimal("0.01")))


def _load_mappings(session: Session) -> dict[str, AccountingMapping]:
    rows = session.execute(select(AccountingMapping).where(AccountingMapping.is_active.is_(True))).scalars()
    return {m.fee_type: m for m in rows}


def _check_receivable(row: dict) -> None:
    if row["net_cents"] + row["tax_cents"] != row["gross_cents"]:
        raise ValueError(
            f"应收行恒等式不成立：{row['contract_no']} {row['fee_type']} "
            f"{row['net_cents']}+{row['tax_cents']}!={row['gross_cents']}")


def build_receivable_rows(period: str, data: list[dict], mappings: dict[str, AccountingMapping]) -> list[dict]:
    missing = sorted({d["fee_type"] for d in data if d["fee_type"] not in mappings})
    if missing:
        raise MissingMapping(missing)
    out = []
    for row in data:
        if row["period"] != period:
            continue
        _check_receivable(row)
        mapping = mappings[row["fee_type"]]
        out.append({
            "row_key": f"AR:{row['contract_no']}:{row['fee_type']}:{row['period']}",
            "cells": [row["contract_no"], row["company"], row["fee_type"], row["period"],
                      row["net_cents"], cents_to_yuan(row["net_cents"]),
                      row["tax_cents"], cents_to_yuan(row["tax_cents"]),
                      row["gross_cents"], cents_to_yuan(row["gross_cents"]),
                      mapping.revenue_account, mapping.receivable_account, mapping.tax_account],
            "amount_cents": row["gross_cents"],
        })
    return out


def build_receipt_rows(period: str, data: list[dict]) -> list[dict]:
    out = []
    for row in data:
        if row["period"] != period:
            continue
        out.append({
            "row_key": f"RC:{row['bank_serial']}",
            "cells": [row["bank_serial"], row["received_date"], row["company"], row["installment"],
                      row["amount_cents"], cents_to_yuan(row["amount_cents"])],
            "amount_cents": row["amount_cents"],
        })
    return out


def apply_period_lock(session: Session, period: str, export_type: str,
                      rows: list[dict]) -> tuple[list[list], bool]:
    """比对快照，返回 (最终行, 是否含调整)。"""
    lock = session.get(PeriodLock, period)
    snapshots = {
        s.row_key: s for s in session.execute(
            select(ExportSnapshot).where(ExportSnapshot.period == period,
                                         ExportSnapshot.export_type == export_type)
        ).scalars()
    }
    is_adjustment = lock is not None and bool(snapshots)
    output: list[list] = []
    current_keys = set()

    for row in rows:
        current_keys.add(row["row_key"])
        snap = snapshots.get(row["row_key"])
        if snap is None:
            output.append(row["cells"] + (["新增"] if is_adjustment else [""]) + ["", ""])
            if not is_adjustment:
                session.add(ExportSnapshot(period=period, export_type=export_type,
                                           row_key=row["row_key"], amount_cents=row["amount_cents"]))
            continue
        if snap.amount_cents == row["amount_cents"]:
            output.append(row["cells"] + ["", "", ""])
            continue
        diff = row["amount_cents"] - snap.amount_cents
        output.append(row["cells"] + ["", "", ""])              # 保留原行（当前值）
        adjust = list(row["cells"])
        if export_type == "receivable":
            adjust[8] = diff                                    # 价税合计(分)
            adjust[9] = cents_to_yuan(diff)                     # 价税合计(元)
        else:
            adjust[4] = diff                                    # 核销金额(分)
            adjust[5] = cents_to_yuan(diff)                     # 核销金额(元)
        output.append(adjust + [FLAG_CHANGED, snap.amount_cents, diff])
        snap.amount_cents = row["amount_cents"]

    # 快照里存在、本次不存在的行 → 冲销
    for key, snap in snapshots.items():
        if key in current_keys:
            continue
        blank = [""] * (len(RECEIVABLE_HEADER) if export_type == "receivable" else len(RECEIPT_HEADER))
        blank[0] = key
        amount_idx = 8 if export_type == "receivable" else 4
        blank[amount_idx] = -snap.amount_cents
        output.append(blank[:-3] + ["冲销", snap.amount_cents, -snap.amount_cents])

    if lock is None:
        session.add(PeriodLock(period=period, first_exported_at=dt.datetime.now()))
        session.flush()
    return output, is_adjustment


def write_csv(header: list[str], rows: list[list]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def write_xlsx(header: list[str], rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(header)
    for row in rows:
        ws.append(row)
    for idx, title in enumerate(header, start=1):
        if "(元)" in title:
            fmt = "#,##0.00"
        elif "(分)" in title:
            fmt = "#,##0"
        else:
            continue
        for cell in ws.iter_cols(min_col=idx, max_col=idx, min_row=2):
            for c in cell:
                c.number_format = fmt
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export(session: Session, *, period: str, export_type: str, fmt: str, data: list[dict],
           operator: str = "system", out_dir=None) -> dict:
    if export_type == "receivable":
        mappings = _load_mappings(session)
        rows = build_receivable_rows(period, data, mappings)
        header = RECEIVABLE_HEADER
    elif export_type == "receipt":
        rows = build_receipt_rows(period, data)
        header = RECEIPT_HEADER
    else:
        raise ValueError(f"未知导出类型：{export_type}")

    final_rows, is_adjustment = apply_period_lock(session, period, export_type, rows)
    payload = write_csv(header, final_rows) if fmt == "csv" else write_xlsx(header, final_rows)
    total = sum(int(r[8] if export_type == "receivable" else r[4]) for r in final_rows
                if r and str(r[8] if export_type == "receivable" else r[4]).lstrip("-").isdigit())

    run = ExportRun(period=period, export_type=export_type, format=fmt,
                    row_count=len(final_rows), total_cents=total,
                    file_sha256=hashlib.sha256(payload).hexdigest(),
                    operator=operator, is_adjustment=is_adjustment)
    session.add(run)
    session.flush()

    path = None
    if out_dir is not None:
        import pathlib
        path = pathlib.Path(out_dir) / f"{export_type}_{period}{'_adj' if is_adjustment else ''}.{fmt}"
        path.write_bytes(payload)
    return {"run_id": run.id, "rows": len(final_rows), "total_cents": total,
            "sha256": run.file_sha256, "is_adjustment": is_adjustment,
            "payload": payload, "path": path}


def seed_mappings(session: Session, rows: list[tuple[str, str, str, str]]) -> None:
    for fee_type, revenue, receivable, tax in rows:
        session.add(AccountingMapping(fee_type=fee_type, revenue_account=revenue,
                                      receivable_account=receivable, tax_account=tax))
    session.flush()
