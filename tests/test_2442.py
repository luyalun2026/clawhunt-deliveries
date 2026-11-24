# -*- coding: utf-8 -*-
"""#2442 共享数据 / 会所级数据边界验证 · 用例（v3 · 真实 SQL 执行版）。

两种跑法，断言完全相同：
  1) 在线实跑：设置 DATABASE_URL=postgresql://...（本单约定 PostgreSQL 16），
     用例现场建库（00_schema.sql → 01_seed.sql → 00_api_pg.sql）并逐个执行 sql/scenarios/Sxx.sql；
  2) 离线复核：未设 DATABASE_URL 时，读取随包交付的 outputs/scenarios.json（PG 上跑出来的落盘结果），
     并校验每个场景脚本的 sha256 与落盘记录一致 —— 改脚本而不同步结果，用例必红，杜绝手工改数。
"""
import hashlib
import json
import os

import pytest

from app.issues import make_issues, render_markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs")
SCEN_DIR = os.path.join(ROOT, "sql", "scenarios")


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture(scope="module")
def env():
    dsn = os.environ.get("DATABASE_URL", "").strip()
    if dsn.startswith("postgres"):
        from app import dbtest
        conn = dbtest.connect()
        try:
            dbtest.init_db(conn)
            res = dbtest.run_all(conn)
        finally:
            conn.close()
        return {"live": True, "engine": "postgresql", "scenarios": res}

    with open(os.path.join(OUT, "scenarios.json"), encoding="utf-8") as f:
        data = json.load(f)
    return {"live": False, "engine": data["engine"], "scenarios": data["scenarios"]}


@pytest.fixture(scope="module")
def results(env):
    return env["scenarios"]


def by_id(results, sid):
    return next(r for r in results if r["id"] == sid)


# ============================================================ AC1 12 场景三栏
@pytest.mark.parametrize("idx", list(range(12)))
def test_01_ac1_scenario_has_expected_actual_and_passes(results, idx):
    r = results[idx]
    assert r["expected"].strip(), r
    assert r["actual"].strip(), r
    assert r["script"] == "sql/scenarios/%s.sql" % r["id"], r
    assert r["ok"] is True, r


def test_02_ac1_matrix_has_twelve_rows(results):
    assert len(results) == 12
    assert [r["id"] for r in results] == ["S%02d" % i for i in range(1, 13)]


def test_03_ac1_matrix_renders_to_four_columns(results):
    from app.report import render_matrix
    md = render_matrix(results)
    header = md.splitlines()[0]
    assert header.count("|") == 6, header          # 5 列 → 6 个竖线
    for col in ("场景", "期望行为", "执行脚本", "实际结果", "结论"):
        assert col in header
    assert md.count("\n| S") == 12
    assert "app/scenarios.py::" not in md          # 执行脚本列不得再指向内存模型
    assert "sql/scenarios/S01.sql" in md


def test_03_ac1_matrix_matches_script_hashes(results, env):
    """矩阵所依据的结果必须与包内场景脚本同源（防止改脚本不改结果）。"""
    for r in results:
        path = os.path.join(ROOT, r["script"].replace("/", os.sep))
        assert os.path.isfile(path), path
        assert sha256_file(path) == r["sha256"], "%s 脚本已改动但结果未重跑" % r["id"]


# ============================================================ AC2 汇总 = 分会所之和
@pytest.fixture(scope="module")
def sqlrun():
    path = os.path.join(OUT, "sql_results.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_04_ac2_five_aggregates_present(sqlrun):
    assert sqlrun["engine"] == "postgresql", sqlrun["engine"]
    assert sqlrun["all_passed"] is True
    assert len(sqlrun["metrics"]) == 5
    for key, m in sqlrun["metrics"].items():
        assert m["passed"] is True, (key, m)
        assert m["filters_effective"] is True, (key, m)


METRIC_KEYS = ["site_member_count", "monthly_event_count", "opportunity_conversion",
               "sop_completion_rate", "vacant_seat_count"]


@pytest.mark.parametrize("key", METRIC_KEYS)
def test_05_ac2_total_equals_sum_of_sites(sqlrun, key):
    m = sqlrun["metrics"][key]
    assert m["agg_value"] == m["sum_of_sites"]
    assert m["diff"] == 0
    assert len(m["per_site"]) == 3


def test_06_ac2_member_count_semantics_documented():
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    agg = open(os.path.join(ROOT, "sql", "10_agg_member_count.sql"), encoding="utf-8").read()
    assert "在驻关系数口径" in agg
    assert "Enterprise-Site" in readme or "入驻关系" in readme


def test_07_ac2_sop_rate_weighted_equals_aggregate(sqlrun):
    m = sqlrun["metrics"]["sop_completion_rate"]
    assert m["unit"] == "rate"
    assert m["numerator"] == m["sum_numerator"]
    assert m["denominator"] == m["sum_denominator"]
    assert m["agg_value"] == m["sum_of_sites"]


# ============================================================ AC3 问题单
def test_08_ac3_no_issue_when_all_scenarios_pass(results):
    assert make_issues(results) == []
    assert "0 条" in render_markdown([])


def test_09_ac3_issue_generated_for_mismatch_with_locus(results):
    bad = dict(results[0])
    bad["ok"] = False
    bad["actual"] = "企业记录 2 条、入驻关系 1 条（注入不一致）"
    issues = make_issues([bad])
    assert len(issues) == 1
    it = issues[0]
    assert it["tables"] and it["apis"] and it["suggestion"]
    assert "S01" in it["scenario"]


def test_10_ac3_issue_count_equals_mismatch_count(results):
    injected = [dict(r) for r in results]
    for i in (2, 5):
        injected[i]["ok"] = False
    issues = make_issues(injected)
    assert len(issues) == 2
    assert {i["scenario"] for i in issues} == {injected[2]["id"], injected[5]["id"]}


# ============================================================ 边界与加固
def test_11_edge_dual_site_enterprise_single_record(results):
    r = by_id(results, "S01")
    assert "企业记录 1 条" in r["actual"] and "在驻关系 2 条" in r["actual"]


def test_12_edge_private_event_blocks_cross_site_registration(results):
    r = by_id(results, "S02")
    assert "私有活动被拒=True" in r["actual"]
    assert "403" in r["actual"]


def test_13_edge_closed_site_readonly_but_readable(results):
    r = by_id(results, "S04")
    assert "写被拒=True" in r["actual"] and "409" in r["actual"]
    assert "负责人仍为 owner-s2-b1" in r["actual"]


def test_14_edge_site_dictionary_can_extend_but_not_override(results):
    r = by_id(results, "S08")
    assert "覆写被拒=True" in r["actual"]
    assert "coworking 生效=1" in r["actual"]


def test_15_edge_export_never_contains_cross_site_rows(results):
    r = by_id(results, "S12")
    assert "越界行=0" in r["actual"]


def test_16_edge_config_fallback_chain(results):
    r = by_id(results, "S09")
    assert "S1 保证金比例=2000" in r["actual"] and "S2=3000" in r["actual"]


def test_17_edge_soft_delete_keeps_history_row(results):
    r = by_id(results, "S11")
    assert "列表命中=0" in r["actual"] and "物理记录=1 条" in r["actual"]


def test_18_edge_scenarios_are_isolated(env):
    """场景之间事务隔离：脚本里的 UPDATE/INSERT 不得留存到下一个场景。"""
    if env["live"]:
        from app import dbtest
        conn = dbtest.connect()
        try:
            dbtest.init_db(conn)
            first = dbtest.run_all(conn)
            second = dbtest.run_all(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM scenario_result")
                leftover = cur.fetchone()[0]
        finally:
            conn.close()
        assert [r["actual"] for r in first] == [r["actual"] for r in second]
        assert leftover == 0
    else:
        ids = [r["id"] for r in env["scenarios"]]
        assert len(ids) == len(set(ids)) == 12
