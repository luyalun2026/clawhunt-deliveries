# -*- coding: utf-8 -*-
"""场景矩阵渲染：场景编号 | 期望行为 | 执行脚本 | 实际结果 | 结论。

「执行脚本」列直接指向 sql/scenarios/Sxx.sql —— 即真实在 PostgreSQL 上执行过的那份 SQL，
不再是 Python 内存模型函数名。
"""
from __future__ import annotations

from typing import Any


def render_matrix(results: list[dict[str, Any]]) -> str:
    lines = [
        "| 场景 | 期望行为 | 执行脚本 | 实际结果 | 结论 |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            "| {id} {name} | {expected} | `{script}` | {actual} | {verdict} |".format(
                id=r["id"], name=r.get("name", ""), expected=r["expected"],
                script=r.get("script", ""), actual=r["actual"],
                verdict="一致" if r["ok"] else "**不一致**",
            )
        )
    return "\n".join(lines) + "\n"


def render_full(results: list[dict[str, Any]], pg_version: str = "") -> str:
    """矩阵 + 执行环境 + 脚本哈希（哈希用于证明矩阵与所交脚本同源，不可手工改数）。"""
    head = [
        "# 12 个场景执行矩阵（由 tools/run_matrix.py 在 PostgreSQL %s 上自动生成）" % pg_version,
        "",
        "- 执行引擎：**PostgreSQL %s**（本单【统一技术约定】要求的版本）" % pg_version,
        "- 建库脚本：`sql/00_schema.sql`（表结构）→ `sql/01_seed.sql`（虚构数据）→ `sql/00_api_pg.sql`（接口桩函数）",
        "- 每个场景一份 `sql/scenarios/Sxx.sql`，脚本内为真实 SQL / 接口桩调用，",
        "  最后一行把「期望 / 实际 / 是否通过」写入 `scenario_result` 表；本矩阵由 `outputs/scenarios.json` 渲染，未手写任何数字。",
        "- 场景之间用事务隔离：每个场景执行后立即 ROLLBACK，互不污染。",
        "",
    ]
    body = [render_matrix(results), ""]
    foot = ["## 脚本哈希（sha256）", "", "| 场景 | 脚本 | sha256 |", "|---|---|---|"]
    for r in results:
        foot.append("| {id} | `{s}` | `{h}` |".format(id=r["id"], s=r.get("script", ""), h=r.get("sha256", "")))
    foot += ["", "## 汇总", "",
             "- 场景数：%d；通过：%d；不一致：%d" % (
                 len(results), sum(1 for r in results if r["ok"]),
                 sum(1 for r in results if not r["ok"])),
             ""]
    return "\n".join(head + body + foot) + "\n"
