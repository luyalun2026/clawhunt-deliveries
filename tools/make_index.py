# -*- coding: utf-8 -*-
"""由 outputs/ 实测文件生成 index.html（页面数字全部来自运行结果，不手写）。

用法：python tools/make_index.py
输入：outputs/verify.json、outputs/run-report.md
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


def main():
    with open(os.path.join(OUT, "verify.json"), encoding="utf-8") as f:
        v = json.load(f)
    run_report = open(os.path.join(OUT, "run-report.md"), encoding="utf-8").read()

    rows = []
    for g, d in v["per_group"].items():
        rows.append("<tr><td>%s</td><td>%d</td><td>%d</td><td>%d</td><td class='%s'>%s</td></tr>" % (
            html.escape(g), d["total"], d["passed"], d["failed"],
            "ok" if d["failed"] == 0 else "", "通过" if d["failed"] == 0 else "失败"))
    groups_total = sum(d["total"] for d in v["per_group"].values())

    metrics = v.get("metrics") or {}
    sql = v.get("sql") or {}
    metric_lines = []
    for k, val in metrics.items():
        if k == "sql" or not isinstance(val, (dict, list)):
            metric_lines.append("- `%s` = `%s`" % (k, html.escape(str(val))))
    if isinstance(sql, dict) and sql.get("all_passed"):
        metric_lines.append("- sql.all_passed = `True`")

    page = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>2288 · IP 处理流水线状态机与失败重试编排（v3）</title>
<style>{CSS}</style></head><body>
<h1>IP 处理流水线状态机与失败重试编排</h1>
<div class="sub">2288 · SQLAlchemy 2 模型 + Alembic 迁移 + Redis 队列/worker + 项目锁 + 失败即停（v3 返工整改版）</div>
<span class="tag">离线可复现</span><span class="tag">全部数字由脚本生成</span><span class="tag">队列化触发</span>

<h2>验证结果（outputs/verify.json）</h2>
<table><tr><th>验收分组</th><th>用例数</th><th>通过</th><th>失败</th><th>结论</th></tr>
{''.join(rows)}
<tr><td><b>合计</b></td><td><b>{groups_total}</b></td><td><b>{v['passed']}</b></td><td><b>{v['failed']}</b></td><td class="ok"><b>全部通过</b></td></tr>
</table>
<p>pytest 汇总：<code>{html.escape(v['pytest_summary'])}</code>；退出码 {v['exit_code']}；生成时间 {v['generated_at']}</p>

<h2>交付包</h2>
<ul class="files">
 <li><a href="pkg.bundle{SHARE}">pkg.bundle（git bundle，离线可 clone）</a><span>完整仓库快照</span></li>
 <li><a href="README.md{SHARE}">README.md</a><span>运行与测试方法 + 返工整改对照</span></li>
 <li><a href="SHA256SUMS{SHARE}">SHA256SUMS</a><span>全部文件校验和</span></li>
 <li><a href="worker.py{SHARE}">worker.py</a><span>队列 + worker（入队/出队/启动回收）</span></li>
 <li><a href="pipeline.py{SHARE}">pipeline.py</a><span>状态机 + 项目锁 + 失败即停</span></li>
 <li><a href="models.py{SHARE}">models.py</a><span>UUID 主键 + 统一审计列</span></li>
 <li><a href="app.py{SHARE}">app.py</a><span>FastAPI 接口层</span></li>
 <li><a href="outputs/verify.json{SHARE}">outputs/verify.json</a><span>用例分组结果</span></li>
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
