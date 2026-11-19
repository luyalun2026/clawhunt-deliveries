# -*- coding: utf-8 -*-
"""eval_runner —— 会员空间平台 AI 工具评测执行器（EVAL-003 工单）。"""
from .core import Case, CaseResult, RunSummary, run_suite  # noqa: F401
from .adapters import BaseAdapter, EchoMockAdapter, HttpAdapter, build_adapter  # noqa: F401

__all__ = ["Case", "CaseResult", "RunSummary", "run_suite",
           "BaseAdapter", "EchoMockAdapter", "HttpAdapter", "build_adapter"]
__version__ = "1.0.0"
