# -*- coding: utf-8 -*-
"""measure_contrast.py — WCAG 2.1 对比度实测（工具名随输出报告，供偏差清单引用）。"""
from __future__ import annotations

TOOL_NAME = "measure_contrast.py (WCAG 2.1 relative luminance)"


def _hex2rgb(h: str):
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb) -> float:
    r, g, b = (_lin(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    l1 = relative_luminance(_hex2rgb(fg_hex))
    l2 = relative_luminance(_hex2rgb(bg_hex))
    hi, lo = max(l1, l2), min(l1, l2)
    return round((hi + 0.05) / (lo + 0.05), 2)


def required_ratio(font_size_px: float, large_min_px: float = 24.0,
                   body_min: float = 4.5, large_min: float = 3.0) -> float:
    """WCAG 2.1 AA：正文 ≥4.5:1；大字（≥24px，或 ≥18.66px 粗体）≥3:1。"""
    return large_min if font_size_px >= large_min_px else body_min


def judge(fg_hex: str, bg_hex: str, font_size_px: float, **kw) -> dict:
    ratio = contrast_ratio(fg_hex, bg_hex)
    req = required_ratio(font_size_px, **kw)
    return {
        "tool": TOOL_NAME,
        "fg": fg_hex,
        "bg": bg_hex,
        "font_size_px": font_size_px,
        "ratio": ratio,
        "required": req,
        "pass": ratio >= req,
    }
