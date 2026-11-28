# -*- coding: utf-8 -*-
"""一键验证：pytest 全量 + junit + 分组矩阵 + verify.json（数字全部自动提取）。"""
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

t0 = time.time()
proc = subprocess.run(
    [sys.executable, "-m", "pytest", "tests", "-q", "--junitxml=" + str(OUT / "junit.xml")],
    cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
)
tail = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else ""
print(tail)

import xml.etree.ElementTree as ET

tree = ET.parse(OUT / "junit.xml")
root = tree.getroot()
suite = root if root.tag == "testsuite" else root.find("testsuite")
total = int(suite.get("tests", "0"))
failures = int(suite.get("failures", "0")) + int(suite.get("errors", "0"))
passed = total - failures
groups: dict = {}
for case in suite.iter("testcase"):
    cls = (case.get("classname") or "other").rsplit(".", 1)[-1]
    ok = case.find("failure") is None and case.find("error") is None
    g = groups.setdefault(cls, {"total": 0, "passed": 0, "failed": 0})
    g["total"] += 1
    g["passed" if ok else "failed"] += 1

v = {
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "pytest_summary": tail,
    "exit_code": proc.returncode,
    "total": total,
    "passed": passed,
    "failed": failures,
    "per_group": groups,
    "all_groups_passed": failures == 0,
    "failed_cases": [
        c.get("name")
        for c in suite.iter("testcase")
        if c.find("failure") is not None or c.find("error") is not None
    ],
}
(OUT / "verify.json").write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")

lines = [
    "# 运行报告（自动生成）",
    "",
    f"- 生成时间：{v['generated_at']}",
    "- 命令：`python verify.py`（内部 `pytest tests -q --junitxml=outputs/junit.xml`）",
    f"- pytest 汇总：`{tail}`；退出码 {proc.returncode}",
    f"- 用例 {total}，通过 {passed}，失败 {failures}",
    "",
    "| 验收分组 | 用例数 | 通过 | 失败 | 结论 |",
    "|---|---|---|---|---|",
]
for name, g in groups.items():
    lines.append(f"| {name} | {g['total']} | {g['passed']} | {g['failed']} | {'通过' if g['failed']==0 else '失败'} |")
lines.append(f"| **合计** | **{total}** | **{passed}** | **{failures}** | **{'全部通过' if failures==0 else '存在失败'}** |")
(OUT / "run-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
sys.exit(proc.returncode)
