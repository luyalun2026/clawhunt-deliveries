#!/usr/bin/env python3
"""build_churn_labels.py — 校准流失标签生成（工单 S6-CAL-002）

输入：虚构企业时间线 JSON（对接 CRM 的接口桩，见 fixtures/timelines.json）
输出：SQLite 中 calib.churn_label 表 + output/monthly_stats.csv

口径（与 docs/churn_label_spec.md 一一对应）：
  正例 R1  快照日 t 起 90 天观察窗内，会籍到期且到期后 30 天内未生成续约会籍
           -> label=1, label_reason=expiry_no_renewal
  正例 R2  观察窗内员工生命周期变为「已流失」-> label=1, label_reason=member_churned
  排除 E1  快照日处于入会引导期（入会 30 天内）-> label IS NULL, reason=in_onboarding
  排除 E2  快照日会籍已终止 -> label IS NULL, reason=membership_terminated
  排除 E3  观察窗未结束（t+90 > 数据截止日）-> label IS NULL, reason=window_open（不进评估集）
  排除 E4  流失原因为企业注销/迁出 -> label=1, label_reason=non_recoverable

判定优先级：E2 -> E1 -> E3 -> R2/R1（R2 先于 R1）-> label=0
"""
from __future__ import annotations
import argparse, csv, json, os, sqlite3, sys
from datetime import date, timedelta

OBS_WINDOW = 90      # 观察窗天数
ONBOARD_DAYS = 30    # 入会引导期
RENEW_GRACE = 30     # 到期后续约宽限期

DDL = """
CREATE TABLE IF NOT EXISTS churn_label (
    company_pid    TEXT NOT NULL,
    snapshot_date  TEXT NOT NULL,
    label          INTEGER,
    label_reason   TEXT,
    observed_until TEXT NOT NULL,
    PRIMARY KEY (company_pid, snapshot_date)
);
"""

POSITIVE_R1 = "expiry_no_renewal"
POSITIVE_R2 = "member_churned"
EXCL_E1 = "in_onboarding"
EXCL_E2 = "membership_terminated"
EXCL_E3 = "window_open"
POSITIVE_E4 = "non_recoverable"

NON_RECOVERABLE = {"deregistered", "relocated"}  # 注销 / 迁出


def _d(s: str) -> date:
    return date.fromisoformat(s)


def label_one_snapshot(company: dict, snap: str, cutoff: date) -> dict:
    """对单个快照日打标，返回一行 dict（与 churn_label 列对齐）。"""
    t = _d(snap)
    obs_until = t + timedelta(days=OBS_WINDOW)
    row = {
        "company_pid": company["company_pid"],
        "snapshot_date": snap,
        "label": None,
        "label_reason": None,
        "observed_until": obs_until.isoformat(),
    }

    # ---- 排除 E2：快照日会籍已终止 ----
    for m in company.get("memberships", []):
        term = m.get("terminated_on")
        if term and _d(term) <= t:
            row["label_reason"] = EXCL_E2
            return row

    # ---- 排除 E1：入会引导期 ----
    joined = company.get("joined_on")
    if joined and (t - _d(joined)).days < ONBOARD_DAYS:
        row["label_reason"] = EXCL_E1
        return row

    # ---- 排除 E3：观察窗未结束 ----
    if obs_until > cutoff:
        row["label_reason"] = EXCL_E3
        return row

    win_end = obs_until  # t+90，闭区间含当日

    # ---- 正例 R2：员工确认流失（观察窗内生命周期变为已流失）----
    for ev in company.get("employee_events", []):
        d0 = _d(ev["date"])
        if t < d0 <= win_end and ev.get("status") == "churned":
            if ev.get("cause") in NON_RECOVERABLE:
                row["label"], row["label_reason"] = 1, POSITIVE_E4  # E4
            else:
                row["label"], row["label_reason"] = 1, POSITIVE_R2
            return row

    # ---- 正例 R1：会籍到期后 30 天内未续约 ----
    for m in company.get("memberships", []):
        exp = m.get("expiry")
        if not exp:
            continue
        e = _d(exp)
        if t < e <= win_end:
            renewed = any(
                _d(r["start"]) <= e + timedelta(days=RENEW_GRACE)
                and _d(r["start"]) > e
                for r in company.get("memberships", [])
                if r is not m and r.get("start")
            )
            if not renewed:
                row["label"], row["label_reason"] = 1, POSITIVE_R1
                return row

    row["label"], row["label_reason"] = 0, "retained"
    return row


def build_labels(timelines: dict) -> list[dict]:
    cutoff = _d(timelines["data_cutoff"])
    rows = []
    for company in timelines["companies"]:
        for snap in company["snapshots"]:
            rows.append(label_one_snapshot(company, snap, cutoff))
    return rows


def write_sqlite(rows: list[dict], db_path: str) -> None:
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    con.execute("CREATE SCHEMA" if False else "PRAGMA journal_mode=WAL")
    con.execute(DDL)
    con.executemany(
        "INSERT INTO churn_label VALUES (?,?,?,?,?)",
        [(r["company_pid"], r["snapshot_date"], r["label"], r["label_reason"], r["observed_until"]) for r in rows],
    )
    con.commit()
    con.close()


def monthly_stats(rows: list[dict]) -> list[dict]:
    agg: dict[str, list[int]] = {}
    for r in rows:
        month = r["snapshot_date"][:7]
        a = agg.setdefault(month, [0, 0, 0])
        if r["label"] == 1:
            a[0] += 1
        elif r["label"] == 0:
            a[1] += 1
        else:
            a[2] += 1
    return [
        {"month": m, "positive": v[0], "negative": v[1], "excluded_null": v[2]}
        for m, v in sorted(agg.items())
    ]


def write_stats_csv(stats: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["month", "positive", "negative", "excluded_null"])
        w.writeheader()
        w.writerows(stats)


def main() -> int:
    ap = argparse.ArgumentParser(description="生成校准流失标签 calib.churn_label")
    ap.add_argument("--input", required=True, help="时间线 JSON（CRM 接口桩）")
    ap.add_argument("--db", default="churn.db", help="输出 SQLite 路径")
    ap.add_argument("--stats", default="output/monthly_stats.csv", help="样本统计表 CSV")
    args = ap.parse_args()

    timelines = json.load(open(args.input, encoding="utf-8"))
    rows = build_labels(timelines)
    write_sqlite(rows, args.db)
    stats = monthly_stats(rows)
    write_stats_csv(stats, args.stats)

    pos = sum(1 for r in rows if r["label"] == 1)
    neg = sum(1 for r in rows if r["label"] == 0)
    nul = sum(1 for r in rows if r["label"] is None)
    print(f"rows={len(rows)} positive={pos} negative={neg} null={nul} db={args.db} stats={args.stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
