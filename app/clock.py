# -*- coding: utf-8 -*-
"""可注入时钟：测试可用 advance() 模拟 5 分钟过期，生产用真实 UTC 时间。"""
from datetime import datetime, timedelta, timezone

_offset_seconds = 0.0


def reset():
    global _offset_seconds
    _offset_seconds = 0.0


def advance(seconds):
    global _offset_seconds
    _offset_seconds += seconds
    return now()


def now():
    return datetime.now(timezone.utc) + timedelta(seconds=_offset_seconds)


def now_ts():
    return now().timestamp()
