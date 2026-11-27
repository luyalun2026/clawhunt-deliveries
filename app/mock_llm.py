"""OpenAI 兼容模型接口 mock（生产替换点：DocLlmClient）。

- MockLLM：进程内可编程 mock，按脚本逐次返回。
- DocLlmClient：生产形态（OpenAI 兼容 /chat/completions），BASE_URL/MODEL 取
  环境变量 DOC_LLM_BASE_URL / DOC_LLM_MODEL，禁止境外接口。
"""
from __future__ import annotations
import json
import os
import urllib.request
from typing import List, Optional


class MockLLM:
    """脚本化 mock：responses 逐次弹出；末位 None 表示之后一律返回最后一条。"""

    def __init__(self, responses: List[Optional[str]]):
        self.responses = list(responses)
        self.calls: List[str] = []

    def chat(self, prompt: str, system: str) -> str:
        self.calls.append(prompt)
        if len(self.responses) > 1:
            return self.responses.pop(0)
        item = self.responses[0]
        if item is None:
            return "unparseable garbage, not json"
        return item

    @staticmethod
    def ok(fields: dict) -> str:
        return json.dumps({"fields": fields}, ensure_ascii=False)


class DocLlmClient:
    """OpenAI 兼容客户端（生产用）。仅供联调；测试全部走 MockLLM。"""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = base_url or os.environ.get("DOC_LLM_BASE_URL", "")
        self.model = model or os.environ.get("DOC_LLM_MODEL", "doc-llm")

    def chat(self, prompt: str, system: str) -> str:
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
