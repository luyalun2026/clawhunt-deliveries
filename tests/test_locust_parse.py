import os
from perfreport import locust
from perfreport.model import percentile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "samples", "locust", "run")


def test_parse_locust_stats():
    run = locust.parse_locust_csv(P + "_stats.csv", P + "_stats_history.csv", "混合读")
    names = {e.name for e in run.endpoints}
    assert names == {"GET /api/members", "GET /api/prospects", "GET /api/orders/export"}
    assert run.total_requests == sum(e.count for e in run.endpoints)
    assert run.total_requests > 500  # 8 并发 10 秒的短轮也满足
    for e in run.endpoints:
        assert e.p50 <= e.p95 <= e.p99, e.name
        assert 0.0 <= e.error_rate <= 1.0
    assert run.timeline and run.timeline[-1]["t"] >= 5
    assert run.users in (8, 16)


def test_error_rate_matches_failure_ratio():
    run = locust.parse_locust_csv(P + "_stats.csv", None)
    ep = run.endpoint("GET /api/orders/export")
    assert ep.failed > 0
    assert abs(ep.error_rate - ep.failed / ep.count) < 1e-9
    assert run.error_rate == run.total_failed / run.total_requests


def test_percentile_interpolation():
    vals = [1.0, 2.0, 3.0, 4.0]
    assert percentile(vals, 50) == 2.5
    assert percentile(vals, 100) == 4.0
    assert percentile([], 95) == 0.0
