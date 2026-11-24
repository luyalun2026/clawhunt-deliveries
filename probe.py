# -*- coding: utf-8 -*-
"""实测采集：读取 outputs/scenarios.json（PG 上真实执行后的落盘结果）→
生成 ISSUES.md（含执行环境说明）与 outputs/matrix-full.md → 输出 JSON 指标给 verify.py。

注意：本文件**不做任何场景计算**，只消费 tools/run_matrix.py 在 PostgreSQL 上的执行结果。
用法：python probe.py（最后一行是 JSON）
"""
import json
import os

from app.issues import make_issues, render_markdown
from app.report import render_full

PKG = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(PKG, "outputs")
os.makedirs(OUT, exist_ok=True)

with open(os.path.join(OUT, "scenarios.json"), encoding="utf-8") as f:
    payload = json.load(f)
with open(os.path.join(OUT, "sql_results.json"), encoding="utf-8") as f:
    sql = json.load(f)

results = payload["scenarios"]
issues = make_issues(results)

open(os.path.join(OUT, "matrix-full.md"), "w", encoding="utf-8").write(
    render_full(results, payload.get("server_version", "")))

# ---- ISSUES.md：执行环境 + 问题单（返工意见 5：必须写明执行环境，证明不是自证）
env_lines = [
    "# 执行环境与问题单",
    "",
    "## 一、执行环境（本轮 12 个场景与 5+5 汇总 SQL 的真实运行环境）",
    "",
    "- 数据库：**PostgreSQL %s**（`SELECT current_setting('server_version')` 实测值）" % payload.get("server_version", ""),
    "- 连接方式：`DATABASE_URL=postgresql://...`；`tools/run_sql.py` 与 `tools/run_matrix.py` 均通过该连接串取连接",
    "- 建库脚本：`sql/00_schema.sql`（15 张表 + 5 个索引）→ `sql/01_seed.sql`（虚构数据）→ `sql/00_api_pg.sql`（10 个接口桩函数）",
    "- 表结构要点：`site` / `enterprise` / `enterprise_site` / `event` / `opportunity` / `sop_task` / `contact` /",
    "  `contact_owner_history` / `knowledge_article` / `dict_entry` / `site_config` / `group_config` /",
    "  `event_registration` / `referral` / `scenario_result`",
    "- 接口桩（PL/pgSQL，全部读写真实表，无内存模型）：`api_change_contact_owner`、`api_transfer_opportunity`、",
    "  `api_register_event`、`api_read_kb`、`api_upsert_site_dict`、`api_dict_entries`、`api_config`、",
    "  `api_visible_contacts`、`api_read_opportunity_as_site`、`api_assert_site_writable`",
    "- 隔离方式：每个场景在独立事务中执行，读完 `scenario_result` 立即 ROLLBACK（`test_18` 断言场景间无残留）",
    "- 数据性质：全部为虚构数据（会所 S1/S2/S3/S9、企业 E01–E23/E90），不含任何真实企业或个人信息",
    "",
    "## 二、12 个场景的执行结果",
    "",
    "| 场景 | 是否一致 | 实际结果 |",
    "|---|---|---|",
]
for r in results:
    env_lines.append("| %s %s | %s | %s |" % (r["id"], r["name"], "一致" if r["ok"] else "**不一致**", r["actual"]))
env_lines += [
    "",
    "## 三、问题单",
    "",
]

body = render_markdown(issues).replace("# 问题单\n\n", "", 1)
open(os.path.join(PKG, "ISSUES.md"), "w", encoding="utf-8").write("\n".join(env_lines) + body)

print(json.dumps({
    "engine": payload.get("engine"),
    "server_version": payload.get("server_version"),
    "scenarios_total": len(results),
    "scenarios_consistent": sum(1 for r in results if r["ok"]),
    "issues": len(issues),
    "sql_engine": sql.get("engine"),
    "sql_all_passed": sql.get("all_passed"),
    "aggregate_max_diff": max((v.get("diff") or 0) for v in sql.get("metrics", {}).values()),
}, ensure_ascii=False))
