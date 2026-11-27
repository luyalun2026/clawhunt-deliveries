# -*- coding: utf-8 -*-
"""S5-INTEL-012 发布日期解析与发布机构名称规范化（纯函数，标准库实现）。

normalize_date(raw, page_meta, fetched_at) -> (date | None, confidence, source)
normalize_publisher(raw, source, aliases) -> {"canonical": ..., "matched_alias": ...,
                                              "publisher_unverified": bool}
"""
from __future__ import annotations

import calendar
import datetime as _dt
import re
import unicodedata

__all__ = ["normalize_date", "normalize_publisher", "load_aliases", "NEED_MANUAL_DATE"]

NEED_MANUAL_DATE = "need_manual_date"
PUBLISHER_UNVERIFIED = "publisher_unverified"

_CN_DIGITS = {"〇": "0", "零": "0", "一": "1", "二": "2", "三": "3", "四": "4",
              "五": "5", "六": "6", "七": "7", "八": "8", "九": "9"}

_DATE_PATTERNS = [
    # ISO / 带时间 / 点分隔
    (re.compile(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})"), False),
    # 中文：2026年11月3日（可带时间）
    (re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日"), False),
    # 中文缺年份：11月3日 / 发布时间：11-03
    (re.compile(r"(\d{1,2})月(\d{1,2})日"), True),
    (re.compile(r"(?<!\d)(\d{1,2})-(\d{1,2})(?!\d)"), True),
]

_META_KEYS = ("article:published_time", "pubdate", "date", "publishdate")
_URL_PATTERNS = [
    re.compile(r"/(\d{4})/(\d{1,2})/(\d{1,2})/"),
    re.compile(r"/(\d{4})-(\d{1,2})-(\d{1,2})/"),
    re.compile(r"/(\d{4})(\d{2})(\d{2})/"),
]

_DEPT_SUFFIXES = ("处", "中心", "办公室", "科", "股", "分局", "管委会", "社")


def _cn_to_digits(text: str) -> str:
    """二〇二六年十一月三日 → 2026年11月3日（支持 十/二十/三十一 等组合）。"""
    _unit = {"十": 10, "百": 100}
    out, i, n = [], 0, len(text)
    while i < n:
        if text[i] in _CN_DIGITS or text[i] in _unit:
            j = i
            while j < n and (text[j] in _CN_DIGITS or text[j] in _unit):
                j += 1
            seg = text[i:j]
            # 逐位数字（〇/零一二…九）+ 十/百 位权混合解析
            if all(c in _CN_DIGITS for c in seg):
                out.append("".join(_CN_DIGITS[c] for c in seg))
            else:
                total, cur = 0, 0
                for c in seg:
                    if c in _CN_DIGITS:
                        cur = int(_CN_DIGITS[c])
                    else:
                        u = _unit[c]
                        if cur == 0:
                            cur = 1
                        total += cur * u
                        cur = 0
                total += cur
                out.append(str(total))
            i = j
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _mk_date(y: int, m: int, d: int):
    try:
        return _dt.date(y, m, d)
    except ValueError:
        return None


def _parse_iso(value: str):
    v = value.strip().replace("Z", "+00:00")
    try:
        dt = _dt.datetime.fromisoformat(v)
        return dt.date() if dt.tzinfo is None or True else dt.date()
    except ValueError:
        return None


def normalize_date(raw, page_meta=None, fetched_at=None):
    """返回 (date|None, confidence, source)；找不到返回 (None, 0.0, "none")。"""
    page_meta = page_meta or {}
    fetched_at = fetched_at or _dt.datetime.now()
    today = fetched_at.date() if isinstance(fetched_at, _dt.datetime) else fetched_at

    text = ""
    if isinstance(raw, str) and raw.strip():
        text = unicodedata.normalize("NFKC", raw)

    # 1) 正文显式 / 缺年份
    if text:
        cn = _cn_to_digits(text)
        for pat, no_year in _DATE_PATTERNS:
            m = pat.search(cn)
            if not m:
                continue
            if no_year:
                mo, dy = int(m.group(1)), int(m.group(2))
                d = _mk_date(today.year, mo, dy)
                if d is None and mo == 2 and dy == 29:
                    return None, 0.0, "none"  # 闰日推断年不闰 → 宁缺勿错
                if d is not None and d > today:
                    d2 = _mk_date(today.year - 1, mo, dy)
                    if d2 is None:
                        return None, 0.0, "none"
                    return d2, 0.6, "body_inferred_year"
                if d is not None:
                    return d, 0.6, "body_inferred_year"
                continue
            y, mo, dy = int(m.group(1)), int(m.group(2)), int(m.group(3))
            d = _mk_date(y, mo, dy)
            if d is not None and d <= today:
                return d, 0.95, "body"
            if d is not None:
                return d, 0.95, "body"  # 显式年份即使晚于抓取日也如实返回

    # 2) meta 标签
    for key in _META_KEYS:
        for mk, mv in page_meta.items():
            if mk.lower() == key.lower() and isinstance(mv, str) and mv.strip():
                d = _parse_iso(mv)
                if d is not None:
                    return d, 0.9, "meta"
                break

    # 3) URL 路径
    url = str(page_meta.get("url") or "")
    for pat in _URL_PATTERNS:
        m = pat.search(url)
        if m:
            y, mo, dy = int(m.group(1)), int(m.group(2)), int(m.group(3))
            d = _mk_date(y, mo, dy)
            if d is not None:
                return d, 0.85, "url"
            break

    # 4) 失败：绝不静默使用抓取日期
    return None, 0.0, "none"


def load_aliases(path):
    """极简 YAML 别名字典加载（仅依赖标准库；生产可换 PyYAML）。"""
    import json
    cfg = json.load(open(path, encoding="utf-8")) if str(path).endswith(".json") else None
    if cfg is not None:
        return cfg
    # 最小 YAML 子集：canonical: / aliases: [.., ..]
    result, cur = {}, None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            cur = line[:-1].strip()
            result[cur] = {"aliases": []}
        elif line.strip().startswith("- ") and cur:
            result[cur]["aliases"].append(line.strip()[2:].strip().strip("'\""))
    return result


def normalize_publisher(raw, source=None, aliases=None):
    """按别名 YAML 统一机构名；未命中回退来源名并标记 publisher_unverified。"""
    aliases = aliases or {}
    name = ""
    if isinstance(raw, str) and raw.strip():
        name = unicodedata.normalize("NFKC", raw).strip()
    stripped = name
    for suf in _DEPT_SUFFIXES:
        if stripped.endswith(suf) and len(stripped) > len(suf) + 2:
            stripped = stripped[: -len(suf)]
            break
    for canon, info in aliases.items():
        cands = [canon] + list(info.get("aliases", []))
        cands_n = [unicodedata.normalize("NFKC", c).strip() for c in cands]
        if name in cands_n or stripped in cands_n:
            return {"canonical": canon, "matched_alias": name,
                    "publisher_unverified": False}
    fallback = source if isinstance(source, str) and source.strip() else name
    return {"canonical": fallback or "", "matched_alias": None,
            "publisher_unverified": True}
