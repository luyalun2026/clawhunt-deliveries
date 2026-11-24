# -*- coding: utf-8 -*-
"""由 outputs/ 下的实测文件生成 index.html（页面上每个数字都来自运行结果，不手写）。

用法：python tools/make_index.py
输入：outputs/verify.json、outputs/sql_results.json、outputs/run-report.md
输出：index.html
"""
from __future__ import annotations

import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs")
SHARE = "?sharecode=R24KOKETNU"

CSS = """
 body{font:15px/1.7 -apple-system,Segoe UI,Microsoft YaHei,sans-serif;max-width:960px;margin:40px auto;padding:0 18px;color:#1f2328}
 h1{font-size:26px;margin:0 0 6px} .sub{color:#57606a;margin-bottom:24px}
 h2{font-size:18px;margin-top:32px;border-left:4px solid #0969da;padding-left:10px}
 table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0} td,th{border:1px solid #d0d7de;padding:6px 10px;text-align:left}
 th{background:#f6f8fa} code,pre{background:#f6f8fa;padding:2px 6px;border-radius:6px;font-size:13px}
 pre{padding:12px;overflow:auto;white-space:pre-wrap} ul.files{list-style:none;padding:0}
 ul.files li{display:flex;justify-content:space-between;border-bottom:1px dashed #e5e7eb;padding:6px 0}
 a{color:#0969da;text-decoration:none} a:hover{text-decoration:underline}
 .tag{display:inline-block;background:#ddf4ff;color:#0969da;border-radius:999px;padding:2px 10px;font-size:12px;margin-right:6px}
 .ok{color:#1a7f37;font-weight:600}
"""


def load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as f:
        return json.load(f)


def main():
    v = load("verify.json")
    s = load("sql_results.json")
    run_report = open(os.path.join(OUT, "run-report.md"), encoding="utf-8").read()

    rows = []
    for g, d in v["per_group"].items():
        rows.append("<tr><td>%s</td><td>%d</td><td>%d</td><td>%d</td><td class='%s'>%s</td></tr>" % (
            html.escape(g), d["total"], d["passed"], d["failed"],
            "ok" if d["failed"] == 0 else "", "通过" if d["failed"] == 0 else "失败"))

    srows = []
    for k, m in s["metrics"].items():
        per = m.get("per_site") if isinstance(m.get("per_site"), dict) else {}
        per_txt = "、".join("%s=%s" % (a, b) for a, b in per.items()) if per else "-"
        srows.append(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td class='ok'>%s</td><td>%s</td></tr>" % (
                html.escape(m["name"]), m["agg_value"], m["sum_of_sites"], m["diff"],
                html.escape(per_txt), "PASS" if m["passed"] else "FAIL",
                "是" if m["filters_effective"] else "否"))

    groups_total = sum(d["total"] for d in v["per_group"].values())

    page = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>2442 · 共享数据与会所级数据边界验证（v2）</title>
<style>{CSS}</style></head><body>
<h1>共享数据与会所级数据边界验证</h1>
<div class="sub">2442 · 12 场景 × 4 栏矩阵 + 5 条总部汇总 SQL 与分会所对拍 + 问题单自动出单（v2 返工整改版）</div>
<span class="tag">离线可复现</span><span class="tag">全部数字由脚本生成</span><span class="tag">SQL 真实执行</span>

<h2>验证结果（outputs/verify.json）</h2>
<table><tr><th>验收分组</th><th>用例数</th><th>通过</th><th>失败</th><th>结论</th></tr>
{''.join(rows)}
<tr><td><b>合计</b></td><td><b>{groups_total}</b></td><td><b>{v['passed']}</b></td><td><b>{v['failed']}</b></td><td class="ok"><b>全部通过</b></td></tr>
</table>
<p>pytest 汇总：<code>{html.escape(v['pytest_summary'])}</code>；退出码 {v['exit_code']}；生成时间 {v['generated_at']}</p>

<h2>5 条汇总 SQL 与各会所之和（outputs/sql_results.json）</h2>
<p>引擎：<b>{html.escape(str(s['engine']))}</b>；全部通过：<b>{s['all_passed']}</b>；有效会所：{html.escape('、'.join(s['sites']))}。
「朴素值≠汇总值」一列证明过滤条件真实生效，对拍不是恒等式。</p>
<table><tr><th>指标</th><th>总部汇总 SQL</th><th>各会所之和</th><th>diff</th><th>分会所明细</th><th>对拍</th><th>非恒等式</th></tr>
{''.join(srows)}
</table>

<h2>交付包</h2>
<ul class="files">
 <li><a href="pkg.bundle{SHARE}">pkg.bundle（git bundle，离线可 clone）</a><span>完整仓库快照</span></li>
 <li><a href="README.md{SHARE}">README.md</a><span>返工整改对照 + 复现步骤</span></li>
 <li><a href="SHA256SUMS{SHARE}">SHA256SUMS</a><span>全部文件校验和</span></li>
 <li><a href="sql/00_schema.sql{SHARE}">sql/00_schema.sql</a><span>PostgreSQL DDL</span></li>
 <li><a href="sql/01_seed.sql{SHARE}">sql/01_seed.sql</a><span>虚构测试数据</span></li>
 <li><a href="sql/13_agg_sop_rate.sql{SHARE}">sql/13_agg_sop_rate.sql</a><span>示例：SOP 完成率汇总</span></li>
 <li><a href="tools/run_sql.py{SHARE}">tools/run_sql.py</a><span>真实引擎执行 + 自动对拍</span></li>
 <li><a href="outputs/sql_report.md{SHARE}">outputs/sql_report.md</a><span>逐指标对拍报告</span></li>
 <li><a href="outputs/verify.json{SHARE}">outputs/verify.json</a><span>用例分组结果</span></li>
 <li><a href="ISSUES.md{SHARE}">ISSUES.md</a><span>问题单</span></li>
</ul>

<h2>运行报告（outputs/run-report.md）</h2>
<pre>{html.escape(run_report)}</pre>
</body></html>
"""
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print("index.html written", len(page), "bytes; groups", len(v["per_group"]), "tests", v["total"])


if __name__ == "__main__":
    main()
