# -*- coding: utf-8 -*-
"""只读 HTTP 客户端：结构性禁止写操作。

只暴露 get()；任何写方法直接 raise，避免调用方误用。
生产环境把 base_url 指向真实服务即可，业务代码无需改动。
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

WRITE_METHODS = ("post", "put", "patch", "delete")


class ReadOnlyViolation(RuntimeError):
    pass


class ReadOnlyClient:
    def __init__(self, base_url: str = "", timeout: float = 10.0, fixtures: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.fixtures = fixtures          # 指向夹具目录时走离线模式
        self.calls: list[str] = []        # 调用记录，供测试断言方法集

    # ---------------------------------------------------------- 唯一出口
    def get(self, path: str, params: dict | None = None):
        self.calls.append("GET")
        if self.fixtures:
            return self._get_fixture(path)
        url = self.base_url + path
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _get_fixture(self, path: str):
        import os
        name = path.strip("/").replace("/", "_") or "root"
        fp = os.path.join(self.fixtures, name + ".json")
        if not os.path.exists(fp):
            raise FileNotFoundError(f"夹具缺失：{fp}")
        with open(fp, encoding="utf-8") as f:
            return json.load(f)

    # ---------------------------------------------------------- 写操作：一律拒绝
    def post(self, *a, **k):
        raise ReadOnlyViolation("read-only client: POST 被禁止")

    def put(self, *a, **k):
        raise ReadOnlyViolation("read-only client: PUT 被禁止")

    def patch(self, *a, **k):
        raise ReadOnlyViolation("read-only client: PATCH 被禁止")

    def delete(self, *a, **k):
        raise ReadOnlyViolation("read-only client: DELETE 被禁止")

    # ---------------------------------------------------------- 端点（只读）
    def rooms(self):
        return self.get("/api/space/rooms")

    def leases(self):
        return self.get("/api/space/leases")

    def contracts(self):
        return self.get("/api/contracts")

    def dashboard(self, as_of: str):
        return self.get("/api/dashboard/metrics", {"as_of": as_of})
