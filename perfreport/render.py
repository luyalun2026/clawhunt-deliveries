"""单文件 HTML 报告渲染：内嵌 CSS + 内嵌 SVG 图表，无任何外链、无外部脚本。"""
from __future__ import annotations

from html import escape
from typing import Dict, List, Optional

from .model import RunResult

CSS = """
:root{--fg:#1b2430;--muted:#5b6b7c;--line:#d8e0e8;--bg:#fbfcfd;--ok:#1a7f4b;--bad:#b3261e;--acc:#1f5fa9}
*{box-sizing:border-box}
body{margin:0;padding:32px;background:var(--bg);color:var(--fg);font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.sub{color:var(--muted);font-size:13px;margin-bottom:18px}
.kpi{display:flex;gap:14px;flex-wrap:wrap;margin:12px 0 4px}
.card{flex:1 1 150px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:12px 14px}
.card .k{color:var(--muted);font-size:12px}.card .v{font-size:20px;font-weight:600;margin-top:2px}
table{border-collapse:collapse;width:100%;background:#fff;font-size:13px}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:right}
th{background:#f1f5f9;font-weight:600}
td.l,th.l{text-align:left}
.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}
.tag{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;border:1px solid var(--line);background:#fff}
ul{margin:6px 0 0 18px;padding:0}li{margin:3px 0}
.note{color:var(--muted);font-size:12px;margin-top:6px}
"""


def _svg_concurrency(run: RunResult, w: int = 760, h: int = 180) -> str:
    pts = run.timeline
    if not pts:
        return '<p class="note">本次结果文件不含时间序列（Locust 需 --csv 生成 stats_history.csv），并发曲线略。</p>'
    mx_u = max(p["users"] for p in pts) or 1
    mx_r = max((p["rps"] for p in pts), default=1) or 1
    n = max(len(pts) - 1, 1)
    def poly(key, mx):
        out = []
        for i, p in enumerate(pts):
            x = 40 + i * (w - 60) / n
            y = h - 24 - (p[key] / mx) * (h - 48)
            out.append(f"{x:.1f},{y:.1f}")
        return " ".join(out)
    axis = f'<line x1="40" y1="{h-24}" x2="{w-20}" y2="{h-24}" stroke="#c9d3dd"/>'
    users = f'<polyline fill="none" stroke="#1f5fa9" stroke-width="2" points="{poly("users", mx_u)}"/>'
    rps = f'<polyline fill="none" stroke="#b26b00" stroke-width="2" stroke-dasharray="4 3" points="{poly("rps", mx_r)}"/>'
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="并发曲线">'
            f'{axis}{users}{rps}'
            f'<text x="40" y="14" font-size="11" fill="#5b6b7c">并发用户（实线，峰值 {mx_u}）／RPS（虚线，峰值 {mx_r:.1f}）</text>'
            f'<text x="40" y="{h-6}" font-size="11" fill="#5b6b7c">0s</text>'
            f'<text x="{w-90}" y="{h-6}" font-size="11" fill="#5b6b7c">{len(pts)-1}s</text></svg>')


def _svg_latency(run: RunResult, w: int = 760, h: int = 220) -> str:
    if not run.endpoints:
        return ""
    eps = run.endpoints[:8]
    mx = max(max(e.p50, e.p95, e.p99) for e in eps) or 1
    barw = 12
    gap = 6
    group = (w - 120) / max(len(eps), 1)
    parts = [f'<line x1="40" y1="{h-28}" x2="{w-20}" y2="{h-28}" stroke="#c9d3dd"/>']
    colors = {"p50": "#8fb8e0", "p95": "#1f5fa9", "p99": "#0d3b6e"}
    for i, e in enumerate(eps):
        x0 = 50 + i * group
        for j, key in enumerate(("p50", "p95", "p99")):
            v = getattr(e, key)
            bh = (v / mx) * (h - 60)
            x = x0 + j * (barw + gap)
            y = h - 28 - bh
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{barw}" height="{max(bh,0):.1f}" fill="{colors[key]}"/>')
            parts.append(f'<text x="{x+barw/2:.1f}" y="{y-3:.1f}" font-size="9" fill="#5b6b7c" text-anchor="middle">{v:.0f}</text>')
        label = e.name if len(e.name) <= 14 else e.name[:13] + "…"
        parts.append(f'<text x="{x0+ (3*(barw+gap))/2:.1f}" y="{h-10}" font-size="10" fill="#5b6b7c" text-anchor="middle">{escape(label)}</text>')
    legend = ('<text x="40" y="14" font-size="11" fill="#5b6b7c">'
              'P50（浅）／P95（中）／P99（深），单位毫秒</text>')
    return f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="各接口延迟分位">{legend}{"".join(parts)}</svg>'


def build_html(run: RunResult, checks: List[Dict], summary: Dict, prev: Optional[RunResult] = None,
               title: str = "性能测试报告", environment: Optional[Dict[str, str]] = None,
               purpose: str = "") -> str:
    env = environment or {}
    env_rows = "".join(
        f'<tr><td class="l">{escape(k)}</td><td class="l">{escape(str(v))}</td></tr>' for k, v in env.items()
    )
    ep_rows = []
    for e in run.endpoints:
        c95 = next((c for c in checks if c["scope"] == e.name and c["metric"] == "p95"), None)
        p95_prev = "—" if (c95 is None or c95["prev"] is None) else f'{c95["prev"]:.1f}'
        p95_delta = "—" if (c95 is None or c95["delta_pct"] is None) else f'{c95["delta_pct"]:+.1f}%'
        verdict = "—" if c95 is None else ('<span class="ok">达标</span>' if c95["ok"] else '<span class="bad">超阈</span>')
        thr = "—" if c95 is None else f'{c95["threshold"]:.1f}'
        ep_rows.append(
            f'<tr><td class="l">{escape(e.name)}</td><td>{e.count}</td><td>{e.p50:.1f}</td>'
            f'<td>{e.p95:.1f}</td><td>{e.p99:.1f}</td><td>{e.error_rate*100:.2f}%</td>'
            f'<td>{e.rps:.1f}</td><td>{thr}</td><td>{p95_prev}</td><td>{p95_delta}</td><td>{verdict}</td></tr>'
        )
    fail_rows = "".join(
        f'<tr><td class="l">{escape(c["scope"])}</td><td>{escape(str(c["metric"]))}</td>'
        f'<td class="bad">{c["actual"]:.2f}</td><td>{c["threshold"]:.2f}</td></tr>'
        for c in summary["failed_items"]
    ) or '<tr><td class="l" colspan="4">无超阈项</td></tr>'
    reg_rows = "".join(
        f'<tr><td class="l">{escape(c["scope"])}</td><td>{escape(str(c["metric"]))}</td><td>{c["prev"]:.2f}</td>'
        f'<td>{c["actual"]:.2f}</td><td class="bad">{c["delta_pct"]:+.1f}%</td></tr>'
        for c in summary["regressions"]
    ) or '<tr><td class="l" colspan="5">无恶化超过 10% 的指标</td></tr>'

    verdict_cls = "ok" if summary["verdict"] == "PASS" else "bad"
    recs = []
    for c in summary["failed_items"][:5]:
        recs.append(f'{c["scope"]} 的 {c["metric"]} 实测 {c["actual"]:.2f} 高于阈值 {c["threshold"]:.2f}，'
                    f'建议先查该接口的慢查询/外部依赖耗时，再评估扩容或缓存。')
    if summary["regressions"]:
        worst = max(summary["regressions"], key=lambda c: c["delta_pct"])
        recs.append(f'{worst["scope"]} 的 {worst["metric"]} 较上一轮恶化 {worst["delta_pct"]:+.1f}%，'
                    f'需与本次变更单比对（依赖升级、索引变动、数据量增长）。')
    if not recs:
        recs.append("全部指标在阈值内且无显著恶化，可按当前配置发布；建议把本轮结果归档为下一轮对比基线。")

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<style>{CSS}</style></head><body>
<h1>{escape(title)}</h1>
<div class="sub">场景：{escape(run.scenario or "（未命名场景）")} ｜ 数据来源：{escape(run.source)} ｜ 请求总数：{run.total_requests} ｜ 失败：{run.total_failed}（{run.error_rate*100:.2f}%）</div>
<div class="kpi">
  <div class="card"><div class="k">结论</div><div class="v {verdict_cls}">{escape(str(summary["verdict"]))}</div></div>
  <div class="card"><div class="k">超阈项 / 检查项</div><div class="v">{summary["failed"]} / {summary["total"]}</div></div>
  <div class="card"><div class="k">最差 P95（ms）</div><div class="v">{run.overall_p95:.1f}</div></div>
  <div class="card"><div class="k">总错误率</div><div class="v">{run.error_rate*100:.2f}%</div></div>
  <div class="card"><div class="k">并发用户</div><div class="v">{run.users or "—"}</div></div>
</div>

<h2>一、测试目的</h2>
<p>{escape(purpose or "验证当前版本在目标并发下的延迟分位与错误率是否满足发布阈值，并与上一轮结果对比识别性能回归。")}</p>

<h2>二、测试环境</h2>
<table><tbody>{env_rows or '<tr><td class="l">（未提供环境信息）</td><td class="l"></td></tr>'}</tbody></table>

<h2>三、并发曲线</h2>
{_svg_concurrency(run)}

<h2>四、各接口延迟分位</h2>
{_svg_latency(run)}
<table><thead><tr><th class="l">接口</th><th>请求数</th><th>P50</th><th>P95</th><th>P99</th><th>错误率</th><th>RPS</th>
<th>P95 阈值</th><th>上轮 P95</th><th>Δ</th><th>判定</th></tr></thead>
<tbody>{''.join(ep_rows)}</tbody></table>
<p class="note">单位：毫秒；Δ 为 P95 相对上一轮的相对变化，正值表示变慢。</p>

<h2>五、阈值对比（超阈项）</h2>
<table><thead><tr><th class="l">接口</th><th class="l">指标</th><th>实测</th><th>阈值</th></tr></thead>
<tbody>{fail_rows}</tbody></table>

<h2>六、与上一轮对比（恶化 &gt; 10%）</h2>
<table><thead><tr><th class="l">接口</th><th class="l">指标</th><th>上轮</th><th>本轮</th><th>变化</th></tr></thead>
<tbody>{reg_rows}</tbody></table>

<h2>七、结论与建议</h2>
<ul>{''.join(f'<li>{escape(r)}</li>' for r in recs)}</ul>
<p class="note">本报告由 perfreport 自动生成：单文件、样式与图表全部内联，无外部依赖，可直接转发。</p>
</body></html>
"""
