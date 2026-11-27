# -*- coding: utf-8 -*-
"""S5-INTEL-012 测试：44 条日期用例 + 属性测试 200 组 + 15 条机构用例 + 边界。"""
import datetime as dt
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.normalize import (NEED_MANUAL_DATE, normalize_date, normalize_publisher,
                           load_aliases)

FA = dt.datetime(2026, 11, 27, 10, 0, 0)

# ---------------- AC1: 44 条日期用例（含中文数字、缺年份、跨年） ----------------
EXPLICIT = [
    # (raw, expected_date)
    ("2026-11-03", dt.date(2026, 11, 3)),
    ("2026-11-03 10:20", dt.date(2026, 11, 3)),
    ("2026.11.03", dt.date(2026, 11, 3)),
    ("2026/11/03", dt.date(2026, 11, 3)),
    ("2026/11/3", dt.date(2026, 11, 3)),
    ("2026年11月3日", dt.date(2026, 11, 3)),
    ("2026年11月3日 10:20", dt.date(2026, 11, 3)),
    ("二〇二六年十一月三日", dt.date(2026, 11, 3)),
    ("二零二六年十一月三日", dt.date(2026, 11, 3)),
    ("发布于 2026-01-01", dt.date(2026, 1, 1)),
    ("2025-12-31 发布", dt.date(2025, 12, 31)),
    ("2026年2月28日", dt.date(2026, 2, 28)),
    ("2024年2月29日", dt.date(2024, 2, 29)),
    ("2026-1-9", dt.date(2026, 1, 9)),
    ("2026-01-09 08:00:00", dt.date(2026, 1, 9)),
    ("2026年1月9日 08:00", dt.date(2026, 1, 9)),
    ("发布时间：2026-05-20", dt.date(2026, 5, 20)),
    ("发布时间：2026年5月20日", dt.date(2026, 5, 20)),
    ("2026年12月31日", dt.date(2026, 12, 31)),
    ("二〇二五年十二月三十一日", dt.date(2025, 12, 31)),
    ("2026-06-15T09:30:00", dt.date(2026, 6, 15)),
    ("2026/07/01 23:59", dt.date(2026, 7, 1)),
    ("二〇二六年一月九日", dt.date(2026, 1, 9)),
    ("二零二六年六月十五日", dt.date(2026, 6, 15)),
    ("2026-08-08（示例日期）", dt.date(2026, 8, 8)),
    ("日期：2026年3月3日", dt.date(2026, 3, 3)),
]

INFERRED = [
    # (raw, fetched_at, expected)  缺年份按抓取年推断，不晚于抓取日
    ("发布时间：11-03", FA, dt.date(2026, 11, 3)),
    ("11月3日", FA, dt.date(2026, 11, 3)),
    ("11-27", FA, dt.date(2026, 11, 27)),
    ("11-28", dt.datetime(2026, 11, 27), dt.date(2025, 11, 28)),  # 未来→回退一年
    ("12-31", dt.datetime(2026, 1, 5), dt.date(2025, 12, 31)),    # 跨年回退
    ("1月1日", dt.datetime(2026, 1, 2), dt.date(2026, 1, 1)),
    ("02-28", dt.datetime(2026, 3, 1), dt.date(2026, 2, 28)),
    ("02-29", dt.datetime(2025, 3, 1), None),  # 推断年非闰年 → need_manual
    ("02-29", dt.datetime(2024, 3, 1), dt.date(2024, 2, 29)),  # 2024 闰年
]

META_URL = [
    ({"article:published_time": "2026-10-01T08:00:00Z"}, dt.date(2026, 10, 1)),
    ({"PubDate": "2026-09-15"}, dt.date(2026, 9, 15)),
    ({"url": "https://news.example.com/2026/08/01/post", "article:published_time": ""}, dt.date(2026, 8, 1)),
    ({"url": "https://x.example.com/2026-07-02/a"}, dt.date(2026, 7, 2)),
    ({"url": "https://x.example.com/20260703/a"}, dt.date(2026, 7, 3)),
]

FAILED = [
    ("正文与 meta 都没有日期", {}),
    ("", {}),
    (None, {}),
    ("乱码 ★★★", {}),
]

ALL_DATE_CASES = [(r, None, None, e) for r, e in EXPLICIT] + \
                 [(r, None, f, e) for r, f, e in INFERRED] + \
                 [(None, m, None, e) for m, e in META_URL if "url" not in m] + \
                 [("", m, None, e) for m, e in META_URL if "url" in m] + \
                 [(r, m, None, None) for r, m in FAILED]

def test_ac1_40plus_date_cases_all_correct():
    assert len(EXPLICIT) + len(INFERRED) + len(META_URL) >= 40
    for raw, meta, fetched, expected in ALL_DATE_CASES:
        d, conf, src = normalize_date(raw, meta or {}, fetched or FA)
        if expected is None:
            assert d is None and conf == 0.0 and src == "none"
        else:
            assert d == expected, (raw, meta, d, expected)

def test_ac1_chinese_digit_variants():
    for raw, exp in EXPLICIT:
        if "〇" in raw or "零" in raw:
            d, _, src = normalize_date(raw, {}, FA)
            assert d == exp and src == "body"

# ---------------- AC2: 属性测试（缺年份推断不晚于抓取日） ----------------
def test_ac2_inferred_never_after_fetched():
    rng = random.Random(20261127)
    for _ in range(200):
        month = rng.randint(1, 12)
        day = rng.randint(1, 28)
        fa = dt.datetime(rng.randint(2020, 2027), rng.randint(1, 12),
                         rng.randint(1, 28))
        d, conf, src = normalize_date(f"{month}-{day}", {}, fa)
        if d is not None:
            assert d <= fa.date(), (month, day, fa, d)

def test_ac2_cross_year_inference():
    d, conf, src = normalize_date("12-31", {}, dt.datetime(2026, 1, 5))
    assert (d, conf, src) == (dt.date(2025, 12, 31), 0.6, "body_inferred_year")

# ---------------- AC3: 找不到返回空并标记 need_manual_date ----------------
def test_ac3_not_found_marks_need_manual():
    for raw, meta in FAILED:
        d, conf, src = normalize_date(raw, meta, FA)
        assert d is None and src == "none"

def test_ac3_fetched_at_never_substituted():
    d, conf, src = normalize_date("没有日期的一段正文", {}, FA)
    assert d != FA.date() or d is None
    assert d is None

# ---------------- 机构规范化 15 条 ----------------
ALIASES = load_aliases(Path(__file__).resolve().parents[1] / "app" / "aliases.yaml")

PUB_CASES = [
    ("示例市科创局", "示例市科技创新局（虚构）", False),
    ("示例市科技创新局（虚构）", "示例市科技创新局（虚构）", False),
    ("示例市科技局创新处", "示例市科技创新局（虚构）", False),
    ("云湖新区", "云湖新区管委会（虚构）", False),
    ("云湖管委会", "云湖新区管委会（虚构）", False),
    ("星洲报", "星洲日报（虚构）", False),
    ("星洲日报社", "星洲日报（虚构）", False),
    ("陌生机构", "示例门户（虚构）", True),
    ("示例市科创局 ", "示例市科技创新局（虚构）", False),  # 尾部空白
]

def test_publisher_15_cases():
    extra = [
        ("示例市科技创新局", "示例市科技创新局（虚构）", False),
        ("示例市科技创新局（虚构）", None, False),
        ("云湖新区管委会（虚构）", None, False),
        ("星洲日报（虚构）", None, False),
        ("云湖新区管委会", "云湖新区管委会（虚构）", False),
        ("未知来源 X", "备选来源（虚构）", True),
    ]
    cases = PUB_CASES + extra
    assert len(cases) >= 15
    for raw, expected, unverified in cases:
        src = expected if expected and unverified else raw
        r = normalize_publisher(raw, src, ALIASES)
        assert r["canonical"] == (expected if expected else raw), (raw, r)
        assert r["publisher_unverified"] is unverified, (raw, r)

def test_publisher_unverified_fallback_uses_source():
    r = normalize_publisher("完全未知机构", "某来源网（虚构）", ALIASES)
    assert r["canonical"] == "某来源网（虚构）"
    assert r["publisher_unverified"] is True

# ---------------- 边界 ----------------
def test_invalid_inputs_do_not_raise():
    for raw in (None, "", "   ", "★★★", "0000-00-00"):
        d, conf, src = normalize_date(raw, {}, FA)
        assert d is None or isinstance(d, dt.date)

def test_fullwidth_normalized():
    d, _, src = normalize_date("２０２６－１１－０３", {}, FA)
    assert d == dt.date(2026, 11, 3)

def test_explicit_future_date_returned_as_is():
    d, conf, src = normalize_date("2027-05-01", {}, FA)
    assert d == dt.date(2027, 5, 1) and src == "body"

def test_meta_preferred_only_after_body():
    d, _, src = normalize_date("2026-06-01", {"article:published_time": "2026-05-01"}, FA)
    assert d == dt.date(2026, 6, 1) and src == "body"
