# -*- coding: utf-8 -*-
"""把同一次运行的 junit.xml 渲染成 HTML 报告（不重跑、不手写数字）。

用法：python tools/junit2html.py report/junit.xml report/report.html
"""
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import escape
from pathlib import Path

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>测试报告 · S3-SALES-056</title>
<style>
 body{{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;margin:0;background:#f6f7f9;color:#1f2329}}
 .wrap{{max-width:1040px;margin:0 auto;padding:28px}}
 h1{{font-size:22px;margin:0 0 6px}}
 .meta{{color:#646a73;font-size:13px;margin-bottom:18px}}
 .cards{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}}
 .card{{background:#fff;border:1px solid #e5e6eb;border-radius:10px;padding:14px 18px;min-width:120px}}
 .card b{{display:block;font-size:24px;line-height:1.2}}
 .ok b{{color:#0f7b3f}} .bad b{{color:#c4314b}} .neu b{{color:#1f2329}}
 table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e5e6eb;border-radius:10px;overflow:hidden}}
 th,td{{text-align:left;padding:8px 12px;font-size:13px;border-bottom:1px solid #f0f1f3}}
 th{{background:#fafbfc;color:#646a73;font-weight:600}}
 tr:last-child td{{border-bottom:none}}
 .pass{{color:#0f7b3f;font-weight:600}} .fail{{color:#c4314b;font-weight:600}}
 code{{font-size:12px;color:#4e5969}}
</style></head><body><div class="wrap">
<h1>招商模块安全测试套件 · HTML 报告</h1>
<div class="meta">来源：<code>{source}</code>（同一次运行）｜生成时间（UTC）：{generated}｜总耗时：{time:.2f}s</div>
<div class="cards">
 <div class="card neu"><b>{tests}</b>用例总数</div>
 <div class="card ok"><b>{passed}</b>通过</div>
 <div class="card bad"><b>{failures}</b>失败</div>
 <div class="card bad"><b>{errors}</b>错误</div>
 <div class="card neu"><b>{skipped}</b>跳过</div>
</div>
<table><thead><tr><th>#</th><th>用例</th><th>类</th><th>耗时(s)</th><th>结果</th></tr></thead><tbody>
{rows}
</tbody></table>
<p class="meta">本报告由 <code>tools/junit2html.py</code> 从同一次 pytest 运行产出的 junit.xml 渲染，数字与 junit.xml 完全一致。</p>
</div></body></html>
"""


def main(argv):
    if len(argv) < 3:
        print("用法: python tools/junit2html.py <junit.xml> <out.html>")
        return 2
    src, dst = Path(argv[1]), Path(argv[2])
    root = ET.parse(src).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    rows, total = [], 0
    agg = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "time": 0.0}
    for suite in suites:
        for name in agg:
            agg[name] += float(suite.get(name, 0) or 0)
        for case in suite.findall("testcase"):
            total += 1
            status, cls = "PASS", "pass"
            if case.find("failure") is not None:
                status, cls = "FAIL", "fail"
            elif case.find("error") is not None:
                status, cls = "ERROR", "fail"
            elif case.find("skipped") is not None:
                status, cls = "SKIP", ""
            rows.append("<tr><td>%d</td><td><code>%s</code></td><td>%s</td><td>%.3f</td>"
                        "<td class=\"%s\">%s</td></tr>" % (
                            total, escape(case.get("name", "")),
                            escape(case.get("classname", "")),
                            float(case.get("time", 0) or 0), cls, status))
    agg["tests"] = int(agg["tests"])
    agg["passed"] = agg["tests"] - int(agg["failures"]) - int(agg["errors"]) - int(agg["skipped"])
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(TEMPLATE.format(
        source=src.as_posix(), generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"),
        tests=agg["tests"], passed=agg["passed"], failures=int(agg["failures"]),
        errors=int(agg["errors"]), skipped=int(agg["skipped"]), time=agg["time"],
        rows="\n".join(rows)), encoding="utf-8")
    print("HTML 报告已生成: %s（%d 用例 / %d 通过）" % (dst, agg["tests"], agg["passed"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
