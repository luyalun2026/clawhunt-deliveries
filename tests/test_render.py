import json, os, re
from perfreport import render, thresholds
from perfreport.locust import parse_locust_csv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "samples", "locust", "run")


def _build():
    run = parse_locust_csv(P + "_stats.csv", P + "_stats_history.csv", "混合读")
    thr = thresholds.load_thresholds(os.path.join(ROOT, "thresholds.json"))
    checks = thresholds.compare(run, thr)
    summ = thresholds.overall(checks)
    return run, checks, summ, render.build_html(run, checks, summ, title="T", purpose="P",
                                                environment={"压测机": "本机"})


def test_single_file_no_external_refs():
    _, _, _, html = _build()
    assert "http://" not in html and "https://" not in html
    assert "<script src" not in html
    assert 'rel="stylesheet"' not in html
    assert "@import" not in html
    assert "<iframe" not in html


def test_required_sections_present():
    _, _, _, html = _build()
    for kw in ["测试目的", "测试环境", "并发曲线", "各接口延迟分位", "阈值对比",
               "与上一轮对比", "结论与建议"]:
        assert kw in html, kw
    assert "<svg" in html and "<table" in html


def test_threshold_fail_rendered_red():
    run = parse_locust_csv(P + "_stats.csv", None, "x")
    thr = {"global": {"p95_ms": 1.0, "error_rate": 0.0}, "endpoints": {}}
    checks = thresholds.compare(run, thr)
    summ = thresholds.overall(checks)
    html = render.build_html(run, checks, summ)
    assert summ["verdict"] == "FAIL"
    assert '<span class="bad">UI</span>' not in html
    assert "超阈" in html and 'class="bad"' in html
    assert "高于阈值" in html


def test_prev_columns_rendered():
    run, checks, summ, _ = _build()
    prev = run
    html = render.build_html(run, thresholds.compare(run, thresholds.load_thresholds(
        os.path.join(ROOT, "thresholds.json")), prev), summ, prev=prev)
    assert "上轮 P95" in html
    assert re.search(r"<td>[+-]?0\.0%</td>", html), "同轮对比 Δ 应为 0.0%"


def test_hostile_endpoint_name_escaped():
    # 恶意接口名进入报告必须被转义，不得产生可执行的 HTML/SVG 注入
    run = parse_locust_csv(P + "_stats.csv", None, "x")
    run.endpoints[0].name = '<script>alert(1)</script>'
    thr = thresholds.load_thresholds(os.path.join(ROOT, "thresholds.json"))
    checks = thresholds.compare(run, thr)
    summ = thresholds.overall(checks)
    html = render.build_html(run, checks, summ, title="<img src=x onerror=alert(2)>")
    assert "<script>alert(1)</script>" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;" in html and "&lt;img src=x" in html
