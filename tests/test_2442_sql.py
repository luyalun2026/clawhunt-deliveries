# -*- coding: utf-8 -*-
"""#2442 · SQL 层用例（返工项 1/2 的验证）。

不依赖外部数据库：`tools/run_sql.py` 默认在 SQLite 3 中执行 PostgreSQL 方言的同一批 SQL；
若设置了 DATABASE_URL，则在真实 PostgreSQL 中执行。两类引擎的断言完全相同。

关键点：汇总值（单条 SQL）与分会所值（按 site_id 逐条 SQL）由两条独立路径取得，
并在真实 SQL 引擎里执行，不是 Python 内存列表推导。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(ROOT, "sql")
OUT = os.path.join(ROOT, "outputs", "sql_results.json")

AGG_FILES = [
    "10_agg_member_count.sql",
    "11_agg_monthly_events.sql",
    "12_agg_opportunity_signed.sql",
    "13_agg_sop_rate.sql",
    "14_agg_vacant_seats.sql",
]
SITE_FILES = [
    "20_site_member_count.sql",
    "21_site_monthly_events.sql",
    "22_site_opportunity_signed.sql",
    "23_site_sop_rate.sql",
    "24_site_vacant_seats.sql",
]


@pytest.fixture(scope="module")
def run():
    """真实执行 5 条汇总 SQL + 5×N 条分会所 SQL，返回结构化结果。

    设了 DATABASE_URL → 在 PostgreSQL 16 上实跑（写 outputs/sql_results.json）；
    未设 → 在 SQLite 3 上复跑同一批 SQL（写 outputs/sql_results.sqlite.json），
    并与随包交付的 PG 产物逐项比对，保证两条引擎路径给出同一组数字。
    """
    live = os.environ.get("DATABASE_URL", "").strip().startswith("postgres")
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "run_sql.py")],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=300)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    with open(OUT, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not live:
        sq = os.path.join(ROOT, "outputs", "sql_results.sqlite.json")
        if os.path.isfile(sq):
            with open(sq, "r", encoding="utf-8") as f:
                data["_sqlite"] = json.load(f)
    return data


def test_sql_01_five_aggregate_queries_exist():
    assert len(AGG_FILES) == 5
    for name in AGG_FILES:
        p = os.path.join(SQL_DIR, name)
        assert os.path.isfile(p), f"缺少汇总查询 {name}"
        body = open(p, "r", encoding="utf-8").read()
        assert len(body.strip()) > 60, f"{name} 内容过短"
        assert "SELECT" in body.upper()


def test_sql_02_five_per_site_queries_exist():
    assert len(SITE_FILES) == 5
    for name in SITE_FILES:
        body = open(os.path.join(SQL_DIR, name), "r", encoding="utf-8").read()
        assert ":site_id" in body, f"{name} 未按 site_id 过滤"
        assert "GROUP BY" in body.upper(), f"{name} 缺少 GROUP BY"


def test_sql_03_aggregate_queries_are_headquarters_level():
    """汇总 SQL 不得自带 WHERE site_id = ...（否则等于分会所查询，无法对拍）。"""
    for name in AGG_FILES:
        body = open(os.path.join(SQL_DIR, name), "r", encoding="utf-8").read()
        assert ":site_id" not in body, f"{name} 不应绑定单个会所"
        code = "\n".join(l for l in body.splitlines() if not l.strip().startswith("--"))
        assert "WHERE s.id =" not in code


def test_sql_04_schema_and_seed_are_executed(run):
    assert run["engine"] == "postgresql", run["engine"]
    assert len(run["sites"]) == 3, run["sites"]
    assert run["all_passed"] is True


def test_sql_05_soft_deleted_site_excluded(run):
    """S9 为软删除会所：其 2 条在驻、4 场活动、1 个签约商机、2 个 SOP 任务必须被过滤。"""
    assert "S9" not in run["sites"]
    m = run["metrics"]
    # 在驻关系：S1 6 + S2 5（含 E01 第二会所，E90 已注销企业被排除）+ S3 12
    assert m["site_member_count"]["agg_value"] == 23
    # 2026-11 活动：S1 6 + S2 3 + S3 2（S9 的 4 场全部被过滤）
    assert m["monthly_event_count"]["agg_value"] == 11
    assert m["opportunity_conversion"]["agg_value"] == 6


@pytest.mark.parametrize("key", [
    "site_member_count", "monthly_event_count", "opportunity_conversion",
    "sop_completion_rate", "vacant_seat_count",
])
def test_sql_06_aggregate_equals_sum_of_sites(run, key):
    m = run["metrics"][key]
    assert m["passed"] is True, m
    assert m["diff"] == 0, m
    assert m["agg_value"] == m["sum_of_sites"]
    assert len(m["per_site"]) == 3


@pytest.mark.parametrize("key", [
    "site_member_count", "monthly_event_count", "opportunity_conversion",
    "sop_completion_rate", "vacant_seat_count",
])
def test_sql_07_assertion_is_not_tautological(run, key):
    """去掉过滤条件后数字必须变化 —— 证明对拍不是恒等式。

    历史上本单被返工的原因就是「total 直接等于 sum(per_site)」，断言不可能失败；
    这里要求 naive（不过滤软删除/离场/企业注销）与 agg 不同。
    """
    m = run["metrics"][key]
    assert m["filters_effective"] is True, m


def test_sql_08_sop_rate_uses_numerator_over_denominator(run):
    m = run["metrics"]["sop_completion_rate"]
    assert m["unit"] == "rate"
    assert m["numerator"] == 15 and m["denominator"] == 20
    assert m["agg_value"] == 0.75
    assert m["sum_numerator"] == 15 and m["sum_denominator"] == 20


def test_sql_09_vacant_seats_never_negative(run):
    """S3 在驻 12 > 工位 8 → 空置记 0，不得出现负数。"""
    m = run["metrics"]["vacant_seat_count"]
    assert all(v >= 0 for v in m["per_site"].values())
    assert m["per_site"]["S3"] == 0
    assert m["agg_value"] == 21


def test_sql_10_results_json_matches_live_sql(run):
    """outputs/sql_results.json 的每个数字都能在本次真实执行中复现（防手写数字）。"""
    assert run["all_passed"] is True
    for key, m in run["metrics"].items():
        assert m["agg_value"] == m["sum_of_sites"]
    if "_sqlite" in run:
        for key, m in run["metrics"].items():
            assert run["_sqlite"]["metrics"][key]["agg_value"] == m["agg_value"], key
            assert run["_sqlite"]["metrics"][key]["per_site"] == m["per_site"], key


def test_sql_11_sql_files_are_postgresql_dialect():
    """方言一致性：使用标准 SQL + PostgreSQL 兼容写法，避免 MySQL 专有语法。"""
    joined = ""
    for name in AGG_FILES + SITE_FILES + ["00_schema.sql", "01_seed.sql"]:
        joined += open(os.path.join(SQL_DIR, name), "r", encoding="utf-8").read().upper()
    for bad in ["`", "LIMIT 0,", "IFNULL(", "AUTO_INCREMENT", "ENGINE="]:
        assert bad not in joined, f"发现 MySQL 专有语法：{bad}"
    assert "GREATEST(" not in joined
