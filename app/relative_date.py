# -*- coding: utf-8 -*-
"""相对日期推算：只由程序按发布日期计算，模型输出保留原文片段。

支持模式（与生产提示词一致）：
  自发布之日起 N 日内 / 自印发之日起 N 日内 / 自公告发布之日起 N 个工作日内
  发布之日起 N 日内 / 本通知发布之日起 N 个工作日内
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

REL_PATTERNS = [
    re.compile(r"(?:自)?(?:发布|印发|公告发布|通知发布)之日起\s*(\d+)\s*(个)?\s*(日|天|工作日)内"),
    re.compile(r"(?:自)?(?:发布|印发)之日(?:起)?\s*(\d+)\s*(个)?\s*(日|天|工作日)内"),
]

ABSOLUTE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")


def is_relative(source_text: str) -> bool:
    return any(p.search(source_text) for p in REL_PATTERNS)


def _add_workdays(start: datetime, n: int) -> datetime:
    """加 N 个工作日（跳过周六周日；节假日表由配置注入，此处为简化口径）。"""
    cur = start
    added = 0
    while added < n:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            added += 1
    return cur


def normalize_relative_date(source_text: str, publish_date: datetime):
    """返回 (具体日期 datetime, origin)；origin 恒为「程序推算」（相对日期场景）。"""
    for p in REL_PATTERNS:
        m = p.search(source_text)
        if not m:
            continue
        n, _ge, unit = int(m.group(1)), m.group(2), m.group(3)
        if unit == "工作日":
            return _add_workdays(publish_date, n), "程序推算"
        return publish_date + timedelta(days=n), "程序推算"
    raise ValueError("not a relative date: %r" % source_text)


def parse_absolute(source_text: str):
    """绝对日期 → (datetime, origin=原文)。找不到返回 None。"""
    m = ABSOLUTE.search(source_text)
    if not m:
        return None
    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))), "原文"
