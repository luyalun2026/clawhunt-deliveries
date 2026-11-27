"""S5-DOC-013 测试套件：AC1-AC4 + 边界。全部虚构金额。"""
import ast
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.amount import (
    parse_lower_amount, parse_upper_amount, parse_tax_rate,
    check_and_reconcile, _to_fen, ALLOWED_RATES_BP,
)
from decimal import Decimal

FIXTURES = json.load(open(os.path.join(ROOT, "data", "amount_fixtures.json"),
                          encoding="utf-8"))["fixtures"]


# ---------- AC1：50 条夹具全部解析为期望分整数 ----------
def test_ac1_all_50_fixtures_parse_to_expected_fen():
    assert len(FIXTURES) == 50
    for fx in FIXTURES:
        kind = fx["kind"]
        raw = fx["raw"]
        expect = fx["expect_fen"]
        if kind == "lower":
            got = parse_lower_amount(raw)
        elif kind == "upper":
            got = parse_upper_amount(raw)
        else:
            raise AssertionError(f"unknown kind {kind}")
        assert got == expect, f"{fx['id']} {raw!r}: got {got}, expect {expect}"


# ---------- AC2：大小写不一致 -> amount_case_mismatch ----------
def test_ac2_case_mismatch_flags_and_human_review():
    fx = [{"lower": "120000元", "upper": "壹拾贰万伍仟元整"}]  # 120000 vs 125000
    res = check_and_reconcile("合同金额如夹具所示。", fixtures=fx)
    assert res.amount_case_mismatch is True
    assert res.need_human_review is True


def test_ac2b_case_consistent_no_flag():
    fx = [{"lower": "120000元", "upper": "壹拾贰万元整"}]  # 均 120000
    res = check_and_reconcile("合同金额如夹具所示。", fixtures=fx)
    assert res.amount_case_mismatch is False


# ---------- AC3：只有含税金额与税率 -> 不含税保持空 ----------
def test_ac3_two_items_no_inference():
    text = "价税合计 113000元。税率 13%。"
    res = check_and_reconcile(text)
    assert res.amount_with_tax_fen == 11300000
    assert res.tax_rate_bp == 1300
    assert res.amount_without_tax_fen is None
    assert res.need_human_review is True
    assert any("补录" in n for n in res.notes)


def test_ac3b_three_items_reconcile_ok():
    # 不含税 100000 元、13% -> 含税 113000 元，容差内
    text = "合同总金额（含税）113000元。不含税金额 100000元。税率 13%。"
    res = check_and_reconcile(text)
    assert res.amount_with_tax_fen == 11300000
    assert res.amount_without_tax_fen == 10000000
    assert res.tax_rate_bp == 1300
    assert res.tax_inconsistent is False


# ---------- AC4：无 float 参与金额运算 ----------
def test_ac4_no_float_in_amount_module():
    src = open(os.path.join(ROOT, "app", "amount.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    # 禁止数值字面量为 float
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            raise AssertionError(f"float literal found: {node.value}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float":
            raise AssertionError("float() call found in amount module")
    # Decimal 运算路径存在
    assert "Decimal" in src and "ROUND_HALF_UP" in src


# ---------- 边界 ----------
def test_tax_rate_whitelist():
    assert ALLOWED_RATES_BP == {0, 100, 300, 600, 900, 1300}
    res = check_and_reconcile("税率 5%。")
    assert res.tax_rate_bp == 500
    assert res.tax_rate_unusual is True
    assert res.need_human_review is True


def test_tax_inconsistent_flag():
    # 含税应为 113000，给 120000 -> inconsistent
    text = "价税合计 120000元。不含税金额 100000元。税率 13%。"
    res = check_and_reconcile(text)
    assert res.tax_inconsistent is True
    assert res.need_human_review is True


def test_lower_various_forms():
    assert parse_lower_amount("¥120,000.00") == 12000000
    assert parse_lower_amount("￥12万元") == 12000000
    assert parse_lower_amount("1,234.56元") == 123456
    assert parse_lower_amount("3千元") == 300000


def test_upper_various_forms():
    assert parse_upper_amount("壹拾贰万元整") == 12000000
    assert parse_upper_amount("人民币壹佰贰拾叁万肆仟伍佰陆拾柒圆捌角玖分") == 123456789
    assert parse_upper_amount("伍仟元整") == 500000


def test_to_fen_rounding():
    assert _to_fen(Decimal("0.005")) == 1
    assert _to_fen(Decimal("1.234")) == 123
