"""独立运行被测桩服务（供真实 Locust / k6 压测使用）。

用法：
  DELAY_SCALE=1.0 python tools/stub_server.py --port 8901     # 当前轮
  DELAY_SCALE=2.2 python tools/stub_server.py --port 8902     # 基线轮（更慢）

三个接口与 tools/loadgen.py 完全一致：
  /api/members(4ms) /api/prospects(12ms) /api/orders/export(35ms, 2% 503)
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import loadgen  # noqa: E402
from http.server import ThreadingHTTPServer  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8901)
    a = ap.parse_args()
    loadgen.DELAY_SCALE = float(os.environ.get("DELAY_SCALE", "1.0"))
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), loadgen.Handler)
    print(f"stub on 127.0.0.1:{a.port} delay_scale={loadgen.DELAY_SCALE}", flush=True)
    srv.serve_forever()
