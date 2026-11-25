# -*- coding: utf-8 -*-
"""S6-CAL-002 测试：10 家手工时间线对账 + 观察窗/排除/边界用例。"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from build_churn_labels import build_labels, monthly_stats, label_one_snapshot

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "timelines.json")
CUTOFF = "2026-06-30"

# ---- 手算结果（10 家虚构企业，逐格核对） ----
EXPECTED = {
    ("FP-0001", "2025-03-01"): (1, "expiry_no_renewal"),
    ("FP-0001", "2025-04-01"): (0, "retained"),
    ("FP-0002", "2025-03-01"): (0, "retained"),          # 到期后 15 天续约 -> 未流失
    ("FP-0003", "2025-04-01"): (1, "member_churned"),
    ("FP-0003", "2025-06-01"): (0, "retained"),          # 流失事件早于快照日 -> 不回溯
    ("FP-0004", "2025-06-01"): (None, "in_onboarding"),  # 入会第 12 天
    ("FP-0005", "2025-06-01"): (0, "retained"),          # 到期日在观察窗外 1 天（边界）
    ("FP-0005", "2025-07-01"): (None, "membership_terminated"),
    ("FP-0006", "2025-02-01"): (1, "non_recoverable"),   # 注销
    ("FP-0007", "2025-05-01"): (1, "expiry_no_renewal"),
    ("FP-0008", "2025-02-01"): (0, "retained"),          # 到期后 20 天续约
    ("FP-0009", "2025-07-01"): (1, "member_churned"),
    ("FP-0010", "2026-04-01"): (0, "retained"),          # observed_until 恰等于截止日 -> 已结束
}


def _rows():
    import json
    return build_labels(json.load(open(FIXTURE, encoding="utf-8")))


def test_ac1_hand_timelines_match():
    """AC1：生成的标签与 10 家手工时间线的手算结果逐格一致。"""
    rows = _rows()
    got = {(r["company_pid"], r["snapshot_date"]): (r["label"], r["label_reason"]) for r in rows}
    assert len(rows) == len(EXPECTED), f"行数 {len(rows)} != 手算 {len(EXPECTED)}"
    for k, v in EXPECTED.items():
        assert got[k] == v, f"{k}: 生成 {got[k]} != 手算 {v}"


def test_ac2_window_open_null_and_excluded():
    """AC2：观察窗未结束 -> label 为空，且不进评估集。"""
    rows = _rows()
    import copy, json
    tl = json.load(open(FIXTURE, encoding="utf-8"))
    tl["data_cutoff"] = "2025-06-15"  # 收紧截止日，制造未结束窗口
    rows2 = build_labels(tl)
    open_rows = [r for r in rows2 if r["observed_until"] > "2025-06-15"]
    assert open_rows, "构造后应存在观察窗未结束样本"
    for r in open_rows:
        assert r["label"] is None, f"观察窗未结束却打了标: {r}"
    eval_set = [r for r in rows2 if r["label"] is not None]
    for r in eval_set:
        assert r["observed_until"] <= "2025-06-15", "评估集混入观察窗未结束样本"


def test_ac3_spec_counts():
    """AC3：口径文档列 2 条正例规则与 4 条排除规则（对文档做结构断言）。"""
    doc = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "churn_label_spec.md"), encoding="utf-8").read()
    assert doc.count("- **正例 R") == 2
    assert doc.count("- **排除 E") == 4


def test_boundary_renewal_grace_30_vs_31():
    """边界：到期后第 30 天续约=已续约；第 31 天=未续约。"""
    base = {
        "company_pid": "FP-B", "joined_on": "2024-06-01",
        "memberships": [{"start": "2024-06-01", "expiry": "2025-03-31"}],
        "snapshots": ["2025-03-01"],
    }
    for delta, expect_label in ((30, 0), (31, 1)):
        tl = json_deepcopy(base)
        from datetime import timedelta
        tl["memberships"].append({"start": (_d("2025-03-31") + timedelta(days=delta)).isoformat(), "expiry": "2026-03-31"})
        row = label_one_snapshot(tl, "2025-03-01", _d(CUTOFF))
        assert row["label"] == expect_label, f"E+{delta}: label={row['label']} 期望 {expect_label}"


def test_boundary_observed_until_equals_cutoff():
    """边界：observed_until 恰等于数据截止日 -> 观察窗视为已结束，正常打标。"""
    import json
    tl = {"data_cutoff": "2025-05-30", "companies": [{
        "company_pid": "FP-C", "joined_on": "2024-06-01",
        "memberships": [{"start": "2024-06-01", "expiry": "2026-12-31"}],
        "snapshots": ["2025-03-01"],
    }]}
    rows = build_labels(tl)
    assert rows[0]["label"] == 0 and rows[0]["observed_until"] == "2025-05-30"


def test_boundary_onboarding_day30_not_excluded():
    """边界：快照日=入会第 30 天 -> 不再属于引导期。"""
    tl = {"data_cutoff": "2026-01-01", "companies": [{
        "company_pid": "FP-D", "joined_on": "2025-05-02",
        "memberships": [{"start": "2025-05-02", "expiry": "2026-05-01"}],
        "snapshots": ["2025-06-01"],
    }]}
    row = build_labels(tl)[0]
    assert row["label"] == 0 and row["label_reason"] == "retained"


def test_boundary_churn_at_window_last_day():
    """边界：流失事件恰落在 t+90 当日 -> 计入。"""
    tl = {"data_cutoff": "2026-01-01", "companies": [{
        "company_pid": "FP-E", "joined_on": "2024-06-01",
        "memberships": [{"start": "2024-06-01", "expiry": "2026-12-31"}],
        "employee_events": [{"date": "2025-05-30", "status": "churned", "cause": "service_dissatisfied"}],
        "snapshots": ["2025-03-01"],
    }]}
    row = build_labels(tl)[0]
    assert row["label"] == 1 and row["label_reason"] == "member_churned"


def test_monthly_stats_and_group_split():
    """统计表数字与标签行一致；企业分组切分无跨集泄漏。"""
    rows = _rows()
    stats = monthly_stats(rows)
    assert sum(s["positive"] for s in stats) == sum(1 for r in rows if r["label"] == 1)
    assert sum(s["negative"] for s in stats) == sum(1 for r in rows if r["label"] == 0)
    assert sum(s["excluded_null"] for s in stats) == sum(1 for r in rows if r["label"] is None)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
    from split_by_company import group_split
    tr, va = group_split(rows, ratio=0.5, seed=7)
    ptr = {r["company_pid"] for r in tr}
    pva = {r["company_pid"] for r in va}
    assert not (ptr & pva), "同一企业同时出现在训练集与验证集"


def _d(s):
    from datetime import date
    return date.fromisoformat(s)


def json_deepcopy(o):
    import json
    return json.loads(json.dumps(o))
