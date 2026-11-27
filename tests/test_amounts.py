"""S5-DOC-013 验收测试：4 条 AC 逐条断言。"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.amounts import (parse_lower, parse_upper, parse_rate, check_case,
                         check_tax, is_unusual_rate, extract)
from data.fixtures import LOWER, UPPER, RATE, TOTAL

import pytest


@pytest.mark.parametrize("text,fen", LOWER)
def test_lower_fixtures(text, fen):
    assert parse_lower(text) == fen, f"{text} 期望 {fen}"


@pytest.mark.parametrize("text,fen", UPPER)
def test_upper_fixtures(text, fen):
    assert parse_upper(text) == fen, f"{text} 期望 {fen}"


@pytest.mark.parametrize("text,bp", RATE)
def test_rate_fixtures(text, bp):
    assert parse_rate(text) == bp, f"{text} 期望 {bp}"


def test_ac1_fixture_count():
    assert TOTAL == 50  # AC1：50 条夹具


# AC2：大小写不一致 → amount_case_mismatch
def test_ac2_case_mismatch():
    assert check_case(123456, 123457) is False
    assert check_case(123456, 123456) is True
    assert check_case(123456, None) is True  # 缺一方不比对
    text = ("价税合计：¥1,234.56\n"
            "壹仟贰佰叁拾肆圆伍角柒分\n"
            "不含税金额：¥1,092.00\n"
            "税率：13%")
    assert "amount_case_mismatch" in extract(text)["flags"]


# AC3：只有含税金额与税率 → 不含税金额保持空，不推算
def test_ac3_no_reverse_infer():
    assert check_tax(123400, None, 1300) is None
    text = ("含税总价：¥113,000.00\n"
            "税率：13%")
    r = extract(text)
    assert r["amount_without_tax_fen"] is None
    assert "needs_manual_fill" in r["flags"]
    assert "tax_inconsistent" not in r["flags"]


# AC4：代码中无 float 参与金额运算（AST 静态检查）
def test_ac4_no_float_in_source():
    import ast
    src_path = os.path.join(os.path.dirname(__file__), "..", "app", "amounts.py")
    tree = ast.parse(open(src_path, encoding="utf-8").read())
    floats = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            floats.append(getattr(node, "lineno", "?"))
    assert not floats, f"金额模块出现 float 字面量，行号：{floats}"


def test_tax_consistency_and_unusual():
    # 含税 113000 分 = 不含税 100000 × 1.13
    assert check_tax(113000, 100000, 1300) is True
    assert check_tax(113001, 100000, 1300) is True   # +1 分容差内
    assert check_tax(113002, 100000, 1300) is False  # +2 分超出容差
    assert check_tax(114000, 100000, 1300) is False
    assert is_unusual_rate(1300) is False
    assert is_unusual_rate(500) is True              # 5% 不在白名单
    assert is_unusual_rate(None) is False
