"""离线负载发生器：真实发请求、真实计时，按 Locust CSV 与 k6 JSONL 的官方字段格式落盘。

用法：
  python tools/loadgen.py --out samples/locust/run --seconds 20 --users 16 [--delay-scale 1.35]

产出（前缀 out）：
  out_stats.csv             Locust stats 布局（含 50%/95%/99% 列与 Aggregated 行）
  out_stats_history.csv     Locust history 布局（Timestamp,User Count,...,Requests/s）
  out_failures.csv          Locust failures 布局
  out_k6.jsonl              k6 --out json 布局（Point 行：http_req_duration / http_req_failed）
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from perfreport.model import percentile

BASE_DELAY = {"/api/members": 0.004, "/api/prospects": 0.012, "/api/orders/export": 0.035}
DELAY_SCALE = 1.0
FAIL_AT = {"/api/orders/export": 0.02}  # 2% 请求返回 503，用于演示错误率列


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        if path not in BASE_DELAY:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        time.sleep(BASE_DELAY[path] * DELAY_SCALE * random.uniform(0.6, 1.6))
        if random.random() < FAIL_AT.get(path, 0.0):
            body = b'{"error":"upstream_unavailable"}'
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = json.dumps({"ok": True, "path": path}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # 静默
        return


def run_load(base_url: str, users: int, seconds: float):
    samples = {k: [] for k in BASE_DELAY}
    failures = {k: 0 for k in BASE_DELAY}
    history = []
    lock = threading.Lock()
    stop_at = time.time() + seconds

    def worker(idx: int):
        rnd = random.Random(idx)
        while time.time() < stop_at:
            path = rnd.choice(list(BASE_DELAY))
            t0 = time.perf_counter()
            code = 0
            try:
                with urllib.request.urlopen(base_url + path, timeout=5) as r:
                    r.read()
                    code = r.status
            except urllib.error.HTTPError as e:
                code = e.code
            except Exception:
                code = 0
            ms = (time.perf_counter() - t0) * 1000.0
            with lock:
                samples[path].append((ms, code))
                if code != 200:
                    failures[path] += 1

    threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(users)]
    start = time.time()
    for t in threads:
        t.start()
    seq = []
    while time.time() < stop_at:
        time.sleep(1.0)
        with lock:
            snap = {p: len(v) for p, v in samples.items()}
        seq.append((round(time.time() - start, 1), sum(snap.values())))
    for t in threads:
        t.join(timeout=6)
    # 按秒计算增量 RPS
    prev_total = 0
    for (t, total) in seq:
        history.append({"t": t, "rps": float(total - prev_total), "count": total})
        prev_total = total
    return samples, failures, history


def write_locust(out_prefix: str, samples, failures, history):
    cols = ["Type", "Name", "Request Count", "Failure Count", "Median Response Time",
            "Average Response Time", "Min Response Time", "Max Response Time",
            "Average Content Size", "Requests/s", "Failures/s", "50%", "66%", "75%", "80%",
            "90%", "95%", "98%", "99%", "99.9%", "99.99%", "100%"]
    rows = []
    total_n = total_f = 0
    all_ms = []
    for path, vals in samples.items():
        ms = sorted(v[0] for v in vals)
        n = len(ms)
        f = failures[path]
        total_n += n
        total_f += f
        all_ms.extend(ms)
        if not n:
            continue
        row = {"Type": "GET", "Name": path, "Request Count": n, "Failure Count": f,
               "Median Response Time": round(percentile(ms, 50)), "Average Response Time": round(sum(ms) / n),
               "Min Response Time": round(ms[0]), "Max Response Time": round(ms[-1]),
               "Average Content Size": 64, "Requests/s": round(n / max(history[-1]["t"], 1), 2),
               "Failures/s": round(f / max(history[-1]["t"], 1), 4)}
        for q in ("50", "66", "75", "80", "90", "95", "98", "99", "99.9", "99.99", "100"):
            row[q + "%"] = round(percentile(ms, float(q)))
        rows.append(row)
    all_sorted = sorted(all_ms)
    agg = {"Type": "", "Name": "Aggregated", "Request Count": total_n, "Failure Count": total_f,
           "Median Response Time": round(percentile(all_sorted, 50)),
           "Average Response Time": round(sum(all_sorted) / max(len(all_sorted), 1)),
           "Min Response Time": round(all_sorted[0]) if all_sorted else 0,
           "Max Response Time": round(all_sorted[-1]) if all_sorted else 0,
           "Average Content Size": 64, "Requests/s": round(total_n / max(history[-1]["t"], 1), 2),
           "Failures/s": round(total_f / max(history[-1]["t"], 1), 4)}
    for q in ("50", "66", "75", "80", "90", "95", "98", "99", "99.9", "99.99", "100"):
        agg[q + "%"] = round(percentile(all_sorted, float(q))) if all_sorted else 0
    rows.append(agg)

    with open(out_prefix + "_stats.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    hcols = ["Timestamp", "User Count", "Type", "Name", "Requests/s", "Failures/s",
             "50%", "66%", "75%", "80%", "90%", "95%", "98%", "99%", "99.9%", "99.99%", "100%"]
    base_ts = int(time.time())
    with open(out_prefix + "_stats_history.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=hcols)
        w.writeheader()
        prev_count = 0
        for i, h in enumerate(history):
            row = {"Timestamp": base_ts + i, "User Count": USERS, "Type": "", "Name": "Aggregated",
                   "Requests/s": round(h["rps"], 2), "Failures/s": 0}
            for q in ("50", "66", "75", "80", "90", "95", "98", "99", "99.9", "99.99", "100"):
                row[q + "%"] = round(agg[q + "%"])
            w.writerow(row)
            prev_count = h["count"]

    with open(out_prefix + "_failures.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Method", "Name", "Error", "Occurrences"])
        for path, fcount in failures.items():
            if fcount:
                w.writerow(["GET", path, "HTTPError('503 Server Error: Service Unavailable')", fcount])
        w.writerow(["", "Aggregated", "", sum(failures.values())])


def write_k6_jsonl(path: str, samples):
    with open(path, "w", encoding="utf-8") as f:
        for name, vals in samples.items():
            for ms, code in vals:
                f.write(json.dumps({"type": "Point", "metric": "http_req_duration",
                                    "data": {"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                             "value": round(ms, 3),
                                             "tags": {"name": f"GET {name}", "status": str(code)}}},
                                   ensure_ascii=False) + "\n")
                f.write(json.dumps({"type": "Point", "metric": "http_req_failed",
                                    "data": {"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                             "value": 0 if code == 200 else 1,
                                             "tags": {"name": f"GET {name}", "status": str(code)}}},
                                   ensure_ascii=False) + "\n")


USERS = 16

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=20)
    ap.add_argument("--users", type=int, default=16)
    ap.add_argument("--delay-scale", type=float, default=1.0)
    ap.add_argument("--port", type=int, default=0)
    a = ap.parse_args()
    DELAY_SCALE = a.delay_scale
    USERS = a.users
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    print(f"server on 127.0.0.1:{port}, users={a.users}, seconds={a.seconds}, delay_scale={a.delay_scale}")
    samples, failures, history = run_load(f"http://127.0.0.1:{port}", a.users, a.seconds)
    srv.shutdown()
    write_locust(a.out, samples, failures, history)
    write_k6_jsonl(a.out + "_k6.jsonl", samples)
    total = sum(len(v) for v in samples.values())
    print(f"requests={total} failures={sum(failures.values())} -> {a.out}_stats.csv / _stats_history.csv / _k6.jsonl")
