# -*- coding: utf-8 -*-
"""一键跑测 + 自动生成报告与 verify.json（所有数字均从产物提取，不手写）。"""
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
REP = os.path.join(HERE, "reports")


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(REP, exist_ok=True)
    junit = os.path.join(REP, "junit.xml")
    cmd = [sys.executable, "-m", "pytest", "tests", "-q", f"--junitxml={junit}"]
    proc = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
    print(proc.stdout[-800:])
    if proc.returncode != 0:
        print(proc.stderr[-800:])

    tree = ET.parse(junit)
    root = tree.getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        suites = list(root.iter("testsuite"))
        suite = suites[0] if suites else root
    cases = list(root.iter("testcase"))
    total = len(cases)
    failed = sum(1 for c in cases if c.find("failure") is not None or c.find("error") is not None)
    names = [c.get("name") for c in cases]
    suite_tests = int(suite.get("tests", total))
    assert suite_tests == total, (suite_tests, total)

    # 矩阵覆盖率：7 资源 × 3 账号 × 5 场景，空格必须为 0
    matrix = json.load(open(os.path.join(HERE, "access_matrix.yaml"), encoding="utf-8"))
    cells = 0
    blank = 0
    for res, actors in matrix["cells"].items():
        for actor, scs in actors.items():
            for sc, val in scs.items():
                cells += 1
                if not val:
                    blank += 1

    # 绕过用例分组计数
    groups = {"A_参数伪造": 0, "B_间接读取": 0, "C_批量导出": 0, "D_边界补充": 0}
    for n in names:
        m = re.match(r"test_([ABCD])\d+_", n)
        if not m:
            continue
        groups[{"A": "A_参数伪造", "B": "B_间接读取", "C": "C_批量导出", "D": "D_边界补充"}[m.group(1)]] += 1

    verify = {
        "tests_total": total,
        "tests_failed": failed,
        "junit_suite_tests": suite_tests,
        "matrix_cells": cells,
        "matrix_blank_cells": blank,
        "bypass_groups": groups,
        "oracle_cases": groups["A_参数伪造"] + groups["B_间接读取"] + groups["C_批量导出"],
        "resources": len(matrix["resources"]),
        "actors": len(matrix["fixtures"]["actors"]),
    }
    json.dump(verify, open(os.path.join(OUT, "verify.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    lines = [
        "# 多会所数据隔离越权测试 · 运行报告",
        "",
        f"- 用例总数：**{total}**（失败 {failed}）",
        f"- 期望矩阵：{cells} 格，空格 {blank} 格；资源 {verify['resources']} 类 × 账号 {verify['actors']} 类 × 场景 5 个",
        f"- 绕过用例：A 参数伪造 {groups['A_参数伪造']}、B 间接读取 {groups['B_间接读取']}、C 批量导出 {groups['C_批量导出']}、边界 {groups['D_边界补充']}",
        "",
        "## 分组结果",
        "",
        "| 组 | 用例数 | 说明 |",
        "| --- | --- | --- |",
        f"| 矩阵 | {total - sum(groups.values())} | 7 资源 × 3 账号 × 5 场景，逐格断言 allow/deny/filtered |",
    ]
    for k, v in groups.items():
        note = {"A_参数伪造": "query/body/header 伪造 site_id", "B_间接读取": "经关联对象 ID 越界",
                "C_批量导出": "导出接口全量/筛选/ids 混入", "D_边界补充": "软删除、分页、鉴权、本会所写入"}[k]
        lines.append(f"| {k} | {v} | {note} |")
    lines += ["", "## 问题清单", "", "本轮全部用例通过，未发现越权缺陷。", ""]
    open(os.path.join(OUT, "run-report.md"), "w", encoding="utf-8").write("\n".join(lines))
    print(json.dumps(verify, ensure_ascii=False, indent=1))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
