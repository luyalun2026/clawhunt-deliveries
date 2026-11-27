import json, os, tempfile
from perfreport import cli

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "samples", "locust", "run")


def test_cli_end_to_end_and_json_out():
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "r.html")
        js = os.path.join(d, "s.json")
        code = cli.main(["--locust", P, "--thresholds", os.path.join(ROOT, "thresholds.json"),
                         "--env", os.path.join(ROOT, "env.json"), "--scenario", "s",
                         "-o", out, "--json-out", js])
        assert code in (0, 2)
        assert os.path.getsize(out) > 3000
        doc = json.load(open(js, encoding="utf-8"))
        assert set(doc) == {"run", "checks", "summary"}
        assert doc["summary"]["total"] == 9


def test_cli_previous_round_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        base_js = os.path.join(d, "base.json")
        cli.main(["--locust", P, "--thresholds", os.path.join(ROOT, "thresholds.json"),
                  "-o", os.path.join(d, "b.html"), "--json-out", base_js])
        out = os.path.join(d, "r2.html")
        code = cli.main(["--locust", P, "--thresholds", os.path.join(ROOT, "thresholds.json"),
                         "--previous", base_js, "-o", out])
        assert code == 0
        html = open(out, encoding="utf-8").read()
        assert "上轮 P95" in html
