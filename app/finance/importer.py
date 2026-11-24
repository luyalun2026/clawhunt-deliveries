"""金额解析、方向判定、模板映射与导入编排。

金额：全程 Decimal，不出现 float；输出整数分。
方向：借贷标志为主判据，与金额符号双判据交叉校验，矛盾行计入 failed。
去重：（收款账户, 银行流水号）唯一；批内先聚合，跨批靠唯一约束兜底。
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import re
import time
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import BankImportBatch, BankTransaction

CREDIT_WORDS = {"贷", "贷方", "c", "cr", "credit", "收入", "进账", "存入"}
DEBIT_WORDS = {"借", "借方", "d", "dr", "debit", "支出", "出账", "支取"}

_STRIP = str.maketrans({"￥": "", "¥": "", "$": "", "，": "", ",": "", "　": "", " ": "", " ": ""})


def parse_amount_cents(raw) -> int:
    """'1,234.56' → 123456；'(56.70)' → -5670；空串抛 ValueError。"""
    if raw is None:
        raise ValueError("金额为空")
    if isinstance(raw, (int, Decimal)):
        text = str(raw)
    else:
        text = str(raw)
    text = text.translate(_STRIP).strip()
    if not text:
        raise ValueError("金额为空")
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1]
    if text.startswith("-"):
        negative, text = not negative, text[1:]
    if not re.fullmatch(r"\d+(\.\d+)?", text):
        raise ValueError(f"金额格式非法：{raw!r}")
    value = Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    cents = int((value * 100).to_integral_value(rounding=ROUND_HALF_UP))
    return -cents if negative else cents


def parse_date(raw, formats: list[str]) -> dt.date:
    text = str(raw).strip()
    if isinstance(raw, dt.datetime):
        return raw.date()
    if isinstance(raw, dt.date):
        return raw
    for fmt in formats:
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"日期格式不支持：{raw!r}")


def is_credit(direction: str | None, amount_cents: int) -> tuple[bool, str | None]:
    """返回 (是否贷方, 冲突原因)。

    银行流水常见形态是「金额恒为正 + 单独的借贷方向列」，故方向列优先：
    - 方向=贷：金额必须非负，负数视为矛盾行；
    - 方向=借：金额取绝对值入账（借方本就不入库）；
    - 无方向列时才用金额符号判定。
    """
    word = (direction or "").strip().lower()
    if word:
        if word in CREDIT_WORDS:
            if amount_cents < 0:
                return False, f"贷方标志与负数金额矛盾：{direction!r} / {amount_cents}"
            return True, None
        if word in DEBIT_WORDS:
            return False, None
        return False, f"未知借贷标志：{direction!r}"
    return amount_cents >= 0, None


def map_row(raw: dict, template: dict) -> dict:
    """按模板把源行映射为统一字段。"""
    cols = template["columns"]
    def pick(field):
        source = cols.get(field)
        return raw.get(source) if source else None

    amount = parse_amount_cents(pick("amount"))
    date_value = parse_date(pick("txn_date"), template.get("date_formats") or ["%Y-%m-%d"])
    return {
        "txn_date": date_value,
        "amount_cents": amount,
        "direction": pick("direction"),
        "counterparty_name": (pick("counterparty_name") or "").strip(),
        "counterparty_account": (pick("counterparty_account") or "").strip(),
        "memo": (pick("memo") or "").strip(),
        "bank_serial": str(pick("bank_serial") or "").strip(),
    }


def read_csv(data: bytes, encoding: str = "utf-8-sig") -> list[dict]:
    for enc in (encoding, "utf-8-sig", "gbk"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("无法识别文件编码")
    return list(csv.DictReader(io.StringIO(text)))


def read_xlsx(data: bytes) -> list[dict]:
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    header = [str(h).strip() if h is not None else "" for h in rows[0]]
    return [dict(zip(header, row)) for row in rows[1:] if any(v is not None for v in row)]


def import_rows(session: Session, rows: list[dict], template: dict, account_no: str,
                *, filename: str = "", max_rows: int = 5000) -> BankImportBatch:
    started = time.perf_counter()
    batch = BankImportBatch(
        template_id=template.get("id"), filename=filename, account_no=account_no,
        total_rows=len(rows), status="running")
    session.add(batch)
    session.flush()

    if len(rows) > max_rows:
        batch.status = "failed"
        batch.errors = [{"row": 0, "reason": f"超过单批上限 {max_rows} 行"}]
        session.flush()
        return batch

    errors: list[dict] = []
    seen: set[tuple[str, str]] = set()
    payload = []
    skipped_dup = skipped_debit = 0

    for idx, raw in enumerate(rows, start=2):
        if not any(v not in (None, "") for v in raw.values()):
            continue
        try:
            item = map_row(raw, template)
        except ValueError as exc:
            errors.append({"row": idx, "reason": str(exc)})
            continue
        if not item["bank_serial"]:
            errors.append({"row": idx, "reason": "银行流水号为空"})
            continue
        credit, conflict = is_credit(item["direction"], item["amount_cents"])
        if conflict:
            errors.append({"row": idx, "reason": conflict})
            continue
        if not credit:
            skipped_debit += 1
            continue
        key = (account_no, item["bank_serial"])
        if key in seen:
            skipped_dup += 1
            continue
        seen.add(key)
        existing = session.execute(
            select(BankTransaction).where(
                BankTransaction.account_no == account_no,
                BankTransaction.bank_serial == item["bank_serial"])
        ).scalar_one_or_none()
        if existing:
            skipped_dup += 1
            continue
        payload.append({
            "id": uuid.uuid4(), "batch_id": batch.id, "account_no": account_no,
            "bank_serial": item["bank_serial"], "txn_date": item["txn_date"],
            "amount_cents": abs(item["amount_cents"]), "counterparty_name": item["counterparty_name"],
            "counterparty_account": item["counterparty_account"], "memo": item["memo"],
            "status": "unmatched",
        })

    if payload:
        session.bulk_insert_mappings(BankTransaction, payload)
    batch.added = len(payload)
    batch.skipped_dup = skipped_dup
    batch.skipped_debit = skipped_debit
    batch.failed = len(errors)
    batch.errors = errors[:200]
    batch.status = "succeeded" if not errors else "succeeded_with_errors"
    batch.elapsed_ms = int((time.perf_counter() - started) * 1000)
    session.flush()
    return batch
