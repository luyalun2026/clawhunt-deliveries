# -*- coding: utf-8 -*-
"""被测工具适配器：通用 HTTP 适配器 + echo mock 适配器。

HTTP 适配器调用被测服务的内部评测入口：
    POST {base_url}/internal/eval/{tool}/invoke
请求体固定带 eval_mode=true —— 评测模式下被测服务不得写入真实复核队列、
不得触发任何对外发送。鉴权 token 只从环境变量读取（token_env 给出变量名）。
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from .core import Case


class AdapterError(RuntimeError):
    pass


class BaseAdapter:
    name = "base"

    def invoke(self, case: Case, timeout_s: float) -> dict:
        raise NotImplementedError

    def judge(self, case: Case, out: dict) -> bool:
        """断言判定：默认要求被测服务返回 ok=true 且字段与期望一致。"""
        if not isinstance(out, dict):
            return False
        if not out.get("ok", False):
            return False
        expected = case.expected or {}
        for k, v in expected.items():
            if out.get(k) != v:
                return False
        return True


class EchoMockAdapter(BaseAdapter):
    """离线 mock 适配器：行为由用例 input.behavior 决定，用于自测/CI。"""

    name = "echo"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def invoke(self, case: Case, timeout_s: float) -> dict:
        self.calls.append(case.case_id)
        behavior = (case.input or {}).get("behavior", "ok")
        sleep_s = float((case.input or {}).get("sleep", 0.0))
        if behavior == "timeout":
            # 故意超过单用例超时，触发 core 的重试与 error 判定
            time.sleep(timeout_s + 0.05)
            raise TimeoutError("mock timeout for %s" % case.case_id)
        if sleep_s:
            time.sleep(sleep_s)
        if behavior == "fail":
            return {"ok": False, "reason": "mock assertion failure", "tokens_in": 11, "tokens_out": 7}
        payload = dict(case.expected or {})
        payload.update({"ok": True, "tokens_in": 120, "tokens_out": 40})
        return payload


class HttpAdapter(BaseAdapter):
    """通用 HTTP 适配器（评测模式）。"""

    name = "http"

    def __init__(self, base_url: str, tool: str, token_env: str | None = None,
                 timeout_s: float = 60.0, extra_headers: dict | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.tool = tool
        self.token_env = token_env
        self.timeout_s = timeout_s
        self.extra_headers = extra_headers or {}

    def _token(self) -> str | None:
        if not self.token_env:
            return None
        tok = os.environ.get(self.token_env)
        if not tok:
            raise AdapterError("环境变量 %s 未设置（密钥只从环境变量读取）" % self.token_env)
        return tok

    def invoke(self, case: Case, timeout_s: float) -> dict:
        url = "%s/internal/eval/%s/invoke" % (self.base_url, self.tool)
        body = json.dumps({
            "eval_mode": True,
            "case_id": case.case_id,
            "input": case.input,
            "expected": case.expected,
        }, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        headers.update(self.extra_headers)
        tok = self._token()
        if tok:
            headers["Authorization"] = "Bearer " + tok
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(req, timeout=timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # 4xx/5xx 视为执行错误
            raise AdapterError("HTTP %s from %s" % (exc.code, url)) from exc
        except urllib.error.URLError as exc:
            raise AdapterError("URLError: %s" % exc.reason) from exc


def build_adapter(cfg: dict, tool: str, default_timeout_s: float = 60.0) -> BaseAdapter:
    """按 config/tools.json 的条目装配适配器；接口未就绪时回落到桩。"""
    entry = (cfg.get("tools") or {}).get(tool) or {}
    kind = entry.get("adapter", "http")
    if kind == "echo":
        return EchoMockAdapter()
    if kind == "stub":
        # 接口未就绪：桩适配器返回 ok=True 与期望字段，README 已写明对接点
        class _Stub(EchoMockAdapter):
            name = "stub"
        return _Stub()
    return HttpAdapter(
        base_url=entry.get("base_url", ""),
        tool=entry.get("tool_name", tool),
        token_env=entry.get("token_env"),
        timeout_s=float(entry.get("timeout_s", default_timeout_s)),
        extra_headers=entry.get("headers") or {},
    )
