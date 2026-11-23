# -*- coding: utf-8 -*-
"""一键复现：跑 pytest → 解析 junit → 生成 verify.json 与 run-report.md。

数字全部来自运行结果，不接受手写。用法：python verify.py
"""
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

PKG = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(PKG, "outputs")
JUNIT = os.path.join(OUT, "junit.xml")


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    env = dict(os.environ, PYTHONPATH=PKG)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", f"--junitxml={JUNIT}",
         "-p", "no:cacheprovider"],
        cwd=PKG, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    summary = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else ""
    open(os.path.join(OUT, "pytest-output.txt"), "w", encoding="utf-8").write(
        (proc.stdout or "") + ("\n[stderr]\n" + proc.stderr if proc.stderr else ""))

    root = ET.parse(JUNIT).getroot()
    cases = list(root.iter("testcase"))
    bad = [c for c in cases if c.find("failure") is not None or c.find("error") is not None]
    skipped = [c for c in cases if c.find("skipped") is not None]

    groups: dict[str, dict] = {}
    for c in cases:
        name = c.get("name", "")
        g = "AC1 四类差异检出" if "ac1" in name else \
            "AC2 一致时退出 0 且仅表头" if "ac2" in name else \
            "AC3 只发 GET" if "ac3" in name else \
            "AC4 出租率重算对拍" if "ac4" in name else "边界 5 例 + CLI"
        d = groups.setdefault(g, {"total": 0, "passed": 0, "failed": 0})
        d["total"] += 1
        if c in bad:
            d["failed"] += 1
        else:
            d["passed"] += 1

    diff_rows = []
    csvp = os.path.join(PKG, "out", "reconcile_diff.csv")
    if os.path.exists(csvp):
        import csv as _csv
        with open(csvp, encoding="utf-8-sig") as f:
            diff_rows = list(_csv.DictReader(f))

    verify = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pytest_summary": summary,
        "exit_code": proc.returncode,
        "total": len(cases),
        "passed": len(cases) - len(bad) - len(skipped),
        "failed": len(bad),
        "skipped": len(skipped),
        "per_group": groups,
        "failed_cases": [c.get("name") for c in bad],
        "diff_csv_rows": len(diff_rows),
        "diff_types": sorted({r["type"] for r in diff_rows}),
    }
    json.dump(verify, open(os.path.join(OUT, "verify.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    lines = ["| 验收分组 | 用例数 | 通过 | 失败 |", "|---|---|---|---|"]
    for g, d in groups.items():
        lines.append(f"| {g} | {d['total']} | {d['passed']} | {d['failed']} |")
    lines.append(f"| **合计** | **{len(cases)}** | **{verify['passed']}** | **{verify['failed']}** |")
    matrix = "\n".join(lines)

    report = f"""# 运行报告（自动生成）

- 生成时间：{verify['generated_at']}
- 命令：`python verify.py`（内部 `pytest tests -q`）
- pytest 汇总：`{summary}`；退出码 {proc.returncode}
- 用例 {len(cases)}，通过 {verify['passed']}，失败 {verify['failed']}，跳过 {verify['skipped']}
- 差异 CSV 行数（inconsistent 夹具）：{verify['diff_csv_rows']}
- 差异类型：{', '.join(verify['diff_types']) or '无'}

## 用例 × 结果矩阵

{matrix}

## 口径说明

- 用例数与通过率由 junit.xml 解析得到，未人工填写。
- 出租率按基点（bp）整数比较，容差 50bp；重算口径为「已租工位数 ÷ 可租工位数」。
- 只读性由 `ReadOnlyClient` 结构性保证（写方法直接 raise），并由用例断言调用方法集 ⊆ {{GET}}。
"""
    open(os.path.join(OUT, "run-report.md"), "w", encoding="utf-8").write(report)

    print(summary)
    print(f"passed={verify['passed']} failed={verify['failed']} skipped={verify['skipped']}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
