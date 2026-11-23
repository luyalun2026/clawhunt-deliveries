# -*- coding: utf-8 -*-
"""离线验证器：跑 pytest → 解析 junit → 按验收分组 → 生成 verify.json / matrix.md / run-report.md。

数字全部来自运行结果（junit 用例名与 probe.py 的实测指标），不接受手写。
用法：python verify.py
"""
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

PKG = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(PKG, "outputs")
JUNIT = os.path.join(OUT, "junit.xml")


def load_groups():
    with open(os.path.join(PKG, "groups.json"), encoding="utf-8") as f:
        return json.load(f)


def group_of(name, groups):
    m = re.match(r"test_(\d+)_", name)
    if not m:
        return "其他（边界与加固）"
    n = int(m.group(1))
    for g, ids in groups.items():
        if n in ids:
            return g
    return "其他（边界与加固）"


def run_probe():
    path = os.path.join(PKG, "probe.py")
    if not os.path.exists(path):
        return {}
    proc = subprocess.run([sys.executable, "probe.py"], cwd=PKG, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        return {"probe_error": (proc.stderr or "")[-500:]}
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {"probe_error": "probe 输出非 JSON"}


def main():
    os.makedirs(OUT, exist_ok=True)
    cfg = load_groups()
    groups = cfg.get("groups", {})

    cmd = [sys.executable, "-m", "pytest", "tests", "-q", f"--junitxml={JUNIT}", "-p", "no:cacheprovider"]
    proc = subprocess.run(cmd, cwd=PKG, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out_lines = (proc.stdout or "").strip().splitlines()
    summary_line = out_lines[-1] if out_lines else ""
    open(os.path.join(OUT, "pytest-output.txt"), "w", encoding="utf-8").write(
        (proc.stdout or "") + ("\n[stderr]\n" + proc.stderr if proc.stderr else ""))

    root = ET.parse(JUNIT).getroot()
    cases = list(root.iter("testcase"))
    bad = [c for c in cases if c.find("failure") is not None or c.find("error") is not None]
    skipped = [c for c in cases if c.find("skipped") is not None]

    per = {}
    for c in cases:
        g = group_of(c.get("name", ""), groups)
        d = per.setdefault(g, {"total": 0, "passed": 0, "failed": 0, "skipped": 0})
        d["total"] += 1
        if c in bad:
            d["failed"] += 1
        elif c in skipped:
            d["skipped"] += 1
        else:
            d["passed"] += 1

    order = list(groups) + ["其他（边界与加固）"]
    per = {k: per[k] for k in order if k in per}

    metrics = run_probe()
    verify = {
        "generated_at": subprocess.run(
            [sys.executable, "-c", "import time;print(time.strftime('%Y-%m-%dT%H:%M:%S'))"],
            capture_output=True, text=True).stdout.strip(),
        "pytest_summary": summary_line,
        "exit_code": proc.returncode,
        "total": len(cases),
        "passed": len(cases) - len(bad) - len(skipped),
        "failed": len(bad),
        "skipped": len(skipped),
        "per_group": per,
        "all_groups_passed": all(v["failed"] == 0 for v in per.values()),
        "failed_cases": [c.get("name") for c in bad],
        "metrics": metrics,
    }
    with open(os.path.join(OUT, "verify.json"), "w", encoding="utf-8") as f:
        json.dump(verify, f, ensure_ascii=False, indent=2)

    lines = ["| 验收分组 | 用例数 | 通过 | 失败 | 跳过 | 结论 |", "|---|---|---|---|---|---|"]
    for g, v in per.items():
        lines.append("| %s | %d | %d | %d | %d | %s |" % (g, v["total"], v["passed"], v["failed"], v["skipped"],
                                                      "通过" if v["failed"] == 0 else "失败"))
    lines.append("| **合计** | **%d** | **%d** | **%d** | **%d** | **%s** |" % (
        len(cases), verify["passed"], verify["failed"], verify["skipped"],
        "无失败" if verify["failed"] == 0 else "存在失败"))
    matrix = "\n".join(lines) + "\n"
    open(os.path.join(OUT, "matrix.md"), "w", encoding="utf-8").write(matrix)

    metric_lines = []
    for k, v in metrics.items():
        metric_lines.append("- `%s` = `%s`" % (k, json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v))

    report = [
        "# 运行报告（自动生成）", "",
        "- 生成时间：%s" % verify["generated_at"],
        "- 命令：`python verify.py`（内部 `pytest tests -q` + `python probe.py`）",
        "- pytest 汇总：`%s`；退出码 %d" % (summary_line, proc.returncode),
        "- 用例 %d，通过 %d，失败 %d，跳过 %d（跳过项为需本机安装 Playwright 浏览器的页面层用例）" % (
            len(cases), verify["passed"], verify["failed"], verify["skipped"]), "",
        "## 用例 × 结果矩阵", "", matrix,
        "## 实测指标（probe.py 运行期提取）", "", "\n".join(metric_lines) or "- 无", "",
        "## 口径说明", "",
        "- 用例数与通过率由 junit.xml 解析得到，未人工填写。",
        "- 指标由 probe.py 在真实执行路径中采集，写入 outputs/metrics.json 后并入本报告。",
    ]
    if cfg.get("notes"):
        report += ["- " + n for n in cfg["notes"]]
    open(os.path.join(OUT, "run-report.md"), "w", encoding="utf-8").write("\n".join(report) + "\n")

    print(summary_line)
    print("passed=%d failed=%d skipped=%d groups=%d" % (verify["passed"], verify["failed"], verify["skipped"], len(per)))
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
