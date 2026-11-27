import os
from perfreport import k6

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_parse_k6_jsonl_groups_by_name():
    run = k6.parse_k6_jsonl(os.path.join(ROOT, "samples", "k6", "result.jsonl"))
    names = {e.name for e in run.endpoints}
    assert names == {"GET /api/members", "GET /api/prospects", "GET /api/orders/export"}
    assert run.total_requests == sum(e.count for e in run.endpoints)
    ep = run.endpoint("GET /api/orders/export")
    assert ep.error_rate > 0
    for e in run.endpoints:
        assert e.p50 <= e.p95 <= e.p99


def test_parse_k6_summary_global_only():
    # samples/k6/summary.json 为 k6 v2.4.0 --summary-export 的真实产物
    run = k6.parse_k6_summary(os.path.join(ROOT, "samples", "k6", "summary.json"))
    assert len(run.endpoints) == 1
    ep = run.endpoints[0]
    assert ep.count == 11158
    assert abs(ep.p95 - 45.00126) < 1e-4 and abs(ep.p99 - ep.p95) < 1e-9  # v2.x 无 p(99)，按实现回退 p(95)
    assert abs(run.error_rate - 21 / 11158) < 1e-6
    assert "summary-export" in run.meta["note"]
