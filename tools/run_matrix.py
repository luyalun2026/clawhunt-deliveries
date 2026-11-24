# -*- coding: utf-8 -*-
"""#2442 · 12 场景矩阵生成（PostgreSQL 16 真实执行）

    DATABASE_URL=postgresql://user:pass@127.0.0.1:5432/xxx python tools/run_matrix.py

产出：
    outputs/scenarios.json    每个场景的 期望 / 执行脚本 / 脚本 sha256 / 实际结果 / 是否通过
    outputs/matrix.md         三栏矩阵（场景｜期望行为｜执行脚本｜实际结果｜结论）
    outputs/matrix-full.md    同上，附脚本哈希与执行引擎说明

矩阵里的每一个字都来自数据库执行结果（脚本自己写进 scenario_result 表），Python 侧不拼数字。
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import dbtest  # noqa: E402
from app.report import render_matrix, render_full  # noqa: E402

OUT = os.path.join(ROOT, "outputs")


def main() -> int:
    conn = dbtest.connect()
    try:
        dbtest.init_db(conn)
        results = dbtest.run_all(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('server_version')")
            pg_version = cur.fetchone()[0]
    finally:
        conn.close()

    ok_n = sum(1 for r in results if r["ok"])
    payload = {
        "engine": "postgresql",
        "server_version": pg_version,
        "scenario_count": len(results),
        "passed": ok_n,
        "all_passed": ok_n == len(results) == 12,
        "scenarios": results,
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "scenarios.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(OUT, "matrix-scenarios.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(render_matrix(results))
    with open(os.path.join(OUT, "matrix-full.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(render_full(results, pg_version))

    for r in results:
        print(("PASS" if r["ok"] else "FAIL") + " " + r["id"] + " " + r["actual"])
    print("\n引擎：PostgreSQL %s；通过 %d/%d" % (pg_version, ok_n, len(results)))
    return 0 if payload["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
