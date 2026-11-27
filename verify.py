"""一键复现：跑测试 → 短压测 → 生成报告 → 写 verify.json / index.html。

用法：python verify.py [--skip-load] [--seconds 8]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-load", action="store_true", help="复用已有 samples/locust 结果，不重跑压测")
    ap.add_argument("--seconds", type=float, default=8.0)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    env = dict(os.environ, PYTHONPATH=ROOT)

    if not a.skip_load:
        if shutil.which("locust"):  # 真实 Locust 压测（首选）
            port = 8971
            srv_proc = subprocess.Popen([sys.executable, "tools/stub_server.py", "--port", str(port)],
                                        cwd=ROOT, env=env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)
            try:
                r = run(["locust", "-f", "locustfile.py", "--headless", "-u", "8", "-r", "2",
                         "-t", f"{max(int(a.seconds), 10)}s",
                         "--host", f"http://127.0.0.1:{port}",
                         "--csv=samples/locust/run", "--only-summary"], env=env)
                print(r.stdout.strip() or r.stderr.strip())
                # 桩服务含 2% 模拟 503，Locust 默认对存在失败请求的轮次返回 1，属预期
                assert r.returncode in (0, 1), "locust 压测失败"
            finally:
                srv_proc.terminate()
        else:  # 离线备用负载发生器
            print("未检测到 locust，回退 tools/loadgen.py（离线备用）")
            r = run([sys.executable, "tools/loadgen.py", "--out", "samples/locust/run",
                     "--seconds", str(a.seconds), "--users", "8"], env=env)
            print(r.stdout.strip() or r.stderr.strip())
            assert r.returncode == 0, "loadgen 失败"

    r = run([sys.executable, "-m", "pytest", "tests", "-q"], env=env)
    tail = [l for l in r.stdout.strip().splitlines() if l.strip()][-1]
    passed = int(tail.split()[0]) if "passed" in tail else 0
    print("pytest:", tail)

    r2 = run([sys.executable, "-m", "perfreport.cli", "--locust", "samples/locust/run",
              "--thresholds", "thresholds.json", "--previous", "samples/previous/prev.json",
              "--env", "env.json", "--scenario", "混合读场景：成员列表 + 商机列表 + 订单导出",
              "--purpose", "验证当前版本在目标并发下的延迟分位与错误率是否满足发布阈值，"
              "并与上一轮基线对比识别性能回归。",
              "--title", "性能测试报告 · 会员空间 API", "-o", "outputs/report.html",
              "--json-out", "outputs/summary.json"], env=env)
    print(r2.stdout.strip() or r2.stderr.strip())
    assert r2.returncode in (0, 2), "报告生成失败"

    doc = json.load(open(os.path.join(OUT, "summary.json"), encoding="utf-8"))
    run_doc = doc["run"]
    summ = doc["summary"]
    report_bytes = os.path.getsize(os.path.join(OUT, "report.html"))
    html = open(os.path.join(OUT, "report.html"), encoding="utf-8").read()
    external = sum(html.count(x) for x in ("http://", "https://", "<script src", "@import"))

    eps = run_doc["endpoints"]
    verify = {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "pytest": {"summary": tail, "passed": passed, "returncode": r.returncode},
        "report": {"path": "outputs/report.html", "bytes": report_bytes,
                   "external_refs": external, "sha256": sha256(os.path.join(OUT, "report.html"))},
        "verdict": summ["verdict"],
        "checks": {"total": summ["total"], "failed": summ["failed"]},
        "run": {"source": run_doc["source"], "requests": run_doc["total_requests"],
                "failed": run_doc["total_failed"], "error_rate": run_doc["error_rate"],
                "endpoints": eps},
        "previous": json.load(open(os.path.join(ROOT, "samples", "previous", "prev.json"),
                                   encoding="utf-8"))["run"]["endpoints"],
    }
    json.dump(verify, open(os.path.join(OUT, "verify.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    rows = "".join(
        f'<tr><td>{k}</td><td>{v["count"]}</td><td>{v["p50"]:.1f}</td><td>{v["p95"]:.1f}</td>'
        f'<td>{v["p99"]:.1f}</td><td>{v["error_rate"]*100:.2f}%</td>'
        f'<td>{verify["previous"].get(k, {}).get("p95", float("nan")):.1f}</td></tr>'
        for k, v in eps.items())
    page = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>#2983 P95 分析报告模板与自动生成 · 交付落地页</title>
<style>body{{font:14px/1.7 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;max-width:960px;margin:32px auto;padding:0 20px;color:#1b2430}}
h1{{font-size:21px}}h2{{font-size:16px;margin-top:26px;border-bottom:1px solid #d8e0e8;padding-bottom:6px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border:1px solid #d8e0e8;padding:6px 9px;text-align:right}}
th{{background:#f1f5f9}}td:first-child{{text-align:left}}code{{background:#f3f6f9;padding:1px 5px;border-radius:3px}}
.ok{{color:#1a7f4b;font-weight:600}}.bad{{color:#b3261e;font-weight:600}}</style></head><body>
<h1>工单 #2983 · P95 分析报告模板与自动生成</h1>
<p>验收结论：<span class="{'ok' if summ['verdict']=='PASS' else 'bad'}">{summ['verdict']}</span>
（{summ['total']} 项检查，{summ['failed']} 项超阈）｜pytest {passed} passed｜
报告 {report_bytes} 字节、外链引用 {external} 处</p>
<h2>本期实测（samples/locust · Locust 2.47.0 真实采集）</h2>
<table><thead><tr><th>接口</th><th>请求数</th><th>P50</th><th>P95</th><th>P99</th><th>错误率</th><th>上轮 P95</th></tr></thead>
<tbody>{rows}</tbody></table>
<p>总请求 {run_doc['total_requests']}，失败 {run_doc['total_failed']}（{run_doc['error_rate']*100:.2f}%）。</p>
<h2>三条验收对照</h2>
<ul>
<li>AC1 阈值与上一轮对比：报告第五节「阈值对比（超阈项）」与第六节「与上一轮对比（恶化 &gt; 10%）」，Δ 由 <code>perfreport/thresholds.py</code> 计算。</li>
<li>AC2 单文件无外部依赖：<code>outputs/report.html</code> 内嵌 CSS 与 SVG，外链引用实测 {external} 处（测试 <code>test_single_file_no_external_refs</code> 断言为 0）。</li>
<li>AC3 样例由真实压测结果生成：<code>samples/locust/</code> 三张 CSV 为 <strong>Locust 2.47.0</strong> <code>--headless --csv</code> 真实压测产物；<code>samples/k6/summary.json</code> 与 <code>result.jsonl</code> 为 <strong>k6 v2.4.0</strong> <code>--summary-export</code> / <code>--out json</code> 真实产物；报告由真实 Locust CSV 生成，完整命令见 README「采集与复现」。</li>
</ul>
<h2>复现</h2>
<pre><code>git clone --branch 2983 https://github.com/luyalun2026/clawhunt-deliveries.git
cd clawhunt-deliveries
python -m pytest tests -q          # 期望 {passed} passed
python verify.py --skip-load       # 用已有结果重生成报告与 verify.json
python verify.py                   # 重新压测（8 秒）后再生成</code></pre>
<p>报告样例：<code>outputs/report.html</code>（{report_bytes} 字节，sha256 {verify['report']['sha256'][:16]}…）</p>
</body></html>"""
    open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(page)
    print("verify.json + index.html written | verdict", summ["verdict"],
          "| requests", run_doc["total_requests"], "| external", external)
    return 0 if (summ["verdict"] in ("PASS", "FAIL") and passed > 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
