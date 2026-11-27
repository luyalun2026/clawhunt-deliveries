from perfreport import thresholds
from perfreport.model import Endpoint, RunResult


def _run(p95=50.0, err=0.0):
    return RunResult(source="t", endpoints=[Endpoint(name="GET /api/a", count=100, p50=p95 / 2,
                                                     p95=p95, p99=p95 * 1.5, error_rate=err)],
                     total_requests=100, total_failed=int(err * 100))


def test_pass_and_fail_verdict():
    thr = {"global": {"p50_ms": 60, "p95_ms": 100, "error_rate": 0.05}, "endpoints": {}}
    ok = thresholds.overall(thresholds.compare(_run(50), thr))
    assert ok["verdict"] == "PASS" and ok["failed"] == 0
    bad = thresholds.overall(thresholds.compare(_run(150), thr))
    assert bad["verdict"] == "FAIL"
    metrics = {c["metric"] for c in bad["failed_items"]}
    assert "p95" in metrics
    p95 = [c for c in bad["failed_items"] if c["metric"] == "p95"][0]
    assert p95["actual"] == 150.0


def test_boundary_equal_to_threshold_passes():
    thr = {"global": {"p95_ms": 100, "error_rate": 0.05}, "endpoints": {}}
    s = thresholds.overall(thresholds.compare(_run(100.0, 0.05), thr))
    assert s["verdict"] == "PASS", s


def test_endpoint_override_wins():
    thr = {"global": {"p95_ms": 100}, "endpoints": {"GET /api/a": {"p95_ms": 40}}}
    s = thresholds.overall(thresholds.compare(_run(50), thr))
    assert s["verdict"] == "FAIL"
    assert s["failed_items"][0]["threshold"] == 40.0


def test_previous_delta_and_regression_flag():
    thr = {"global": {"p95_ms": 100, "error_rate": 0.05}, "endpoints": {}}
    checks = thresholds.compare(_run(60), thr, prev=_run(50))
    c95 = [c for c in checks if c["metric"] == "p95"][0]
    assert c95["prev"] == 50.0 and c95["delta_pct"] == 20.0
    s = thresholds.overall(checks)
    assert len(s["regressions"]) == 1


def test_missing_prev_endpoint_yields_none():
    thr = {"global": {"p95_ms": 100}, "endpoints": {}}
    prev = RunResult(source="p", endpoints=[Endpoint(name="GET /other", p95=10)])
    checks = thresholds.compare(_run(60), thr, prev=prev)
    c95 = [c for c in checks if c["metric"] == "p95"][0]
    assert c95["prev"] is None and c95["delta_pct"] is None
