# -*- coding: utf-8 -*-
"""用例集加载：mock 套件用于自测/CI，真实套件从 JSON 文件加载。"""
from __future__ import annotations

import json
import os

from .core import Case

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


def mock_cases(n: int = 20, sleep_s: float = 0.0) -> list[Case]:
    """20 条 mock 用例：偶数号带 sleep，用于验证并发加速。"""
    cases = []
    for i in range(1, n + 1):
        cases.append(Case(
            case_id="MOCK-%03d" % i,
            tags=["smoke"] if i <= 10 else ["full"],
            input={"behavior": "ok", "sleep": sleep_s, "seq": i},
            expected={"seq": i},
        ))
    return cases


def timeout_cases() -> list[Case]:
    """3 条正常 + 1 条必然超时的用例，用于验证重试与退出码 2。"""
    cases = [Case(case_id="TO-%03d" % i, tags=["timeout"], input={"behavior": "ok"},
                  expected={"seq": 0}) for i in range(1, 4)]
    cases.append(Case(case_id="TO-TIMEOUT", tags=["timeout"],
                      input={"behavior": "timeout"}, expected={}))
    return cases


def load_suite(suite_key: str) -> list[Case]:
    """suite_key 支持内置 mock20 / mock_timeout，或指向 JSON 文件的绝对路径。"""
    if suite_key == "mock20":
        return mock_cases(20)
    if suite_key == "mock_timeout":
        return timeout_cases()
    path = suite_key
    if not os.path.isabs(path):
        path = os.path.join(CONFIG_DIR, suite_key)
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    items = raw.get("cases", raw) if isinstance(raw, dict) else raw
    return [Case(case_id=str(it["case_id"]), tags=list(it.get("tags") or []),
                 input=dict(it.get("input") or {}), expected=dict(it.get("expected") or {}))
            for it in items]
