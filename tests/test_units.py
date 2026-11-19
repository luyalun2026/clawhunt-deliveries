# -*- coding: utf-8 -*-
"""单元测试：抽样可复现、标签与用例过滤、token 用量与 latency 落库、HTTP 适配器请求体。"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from eval_runner import Case, EchoMockAdapter, HttpAdapter, run_suite
from eval_runner.core import _sample, _select_cases
from eval_runner.store import Store


def test_sample_is_reproducible_with_fixed_seed():
    cases = [Case(case_id="C%02d" % i) for i in range(20)]
    a = [c.case_id for c in _sample(cases, 5, 42)]
    b = [c.case_id for c in _sample(cases, 5, 42)]
    c = [c.case_id for c in _sample(cases, 5, 7)]
    assert a == b
    assert a != c
    assert len(a) == 5


def test_filter_by_tags_and_case_ids():
    cases = [Case(case_id="C%02d" % i, tags=["smoke"] if i < 5 else ["full"]) for i in range(10)]
    assert len(_select_cases(cases, {"tags": ["smoke"]})) == 5
    assert len(_select_cases(cases, {"case_ids": ["C01", "C09"]})) == 2
    assert len(_select_cases(cases, {"tags": ["smoke"], "case_ids": ["C01"]})) == 1


def test_tokens_and_latency_persisted(tmp_path):
    db = str(tmp_path / "t.db")
    summary = run_suite("mock20", EchoMockAdapter(), options={"db_path": db, "concurrency": 2},
                        cases=[Case(case_id="X1", input={"behavior": "ok"}, expected={"seq": 1})])
    st = Store(db)
    rows = st.results_for_run(summary.run_id)
    st.close()
    assert rows[0]["tokens_in"] == 120 and rows[0]["tokens_out"] == 40
    assert rows[0]["latency_ms"] >= 0
    assert rows[0]["status"] == "passed"
    run = Store(db)
    r = run.conn.execute("SELECT status, exit_code, total FROM eval_run").fetchone()
    run.close()
    assert r["status"] == "finished" and r["exit_code"] == 0 and r["total"] == 1


def test_http_adapter_sends_eval_mode_true(tmp_path):
    captured = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            captured["path"] = self.path
            captured["body"] = body
            out = json.dumps({"ok": True, "seq": 7, "tokens_in": 5, "tokens_out": 2}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):  # 静默
            pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        adapter = HttpAdapter("http://127.0.0.1:%d" % srv.server_port, "kb_assistant")
        res = adapter.invoke(Case(case_id="H1", input={"q": "x"}, expected={"seq": 7}), 5.0)
        assert captured["path"] == "/internal/eval/kb_assistant/invoke"
        assert captured["body"]["eval_mode"] is True
        assert res["ok"] is True and res["tokens_in"] == 5
    finally:
        srv.shutdown()
