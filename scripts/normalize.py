# -*- coding: utf-8 -*-
"""标准化规则：去首尾空格、全角转半角、手机号去国家码。"""
import re
import unicodedata

FULLWIDTH_RE = re.compile(r"[Ａ-Ｚａ-ｚ０-９（）－]")
CC_RE = re.compile(r"^(?:\+86|0086|86)")


def normalize_text(value):
    """通用字段标准化：去首尾空格（含全角空格）+ 全角字母数字转半角。"""
    if value is None:
        return None
    s = str(value).strip().strip("\u3000")
    return FULLWIDTH_RE.sub(lambda m: unicodedata.normalize("NFKC", m.group(0)), s)


def normalize_phone(value):
    """手机号标准化：通用标准化后剥离 +86 / 0086 / 86 国家码前缀。"""
    if value is None:
        return None
    s = normalize_text(value)
    if not s:
        return s
    s2 = CC_RE.sub("", s)
    # 86 前缀剥离后必须仍是合法 11 位手机号才生效，避免误剥如 86123（非法）被破坏
    if s2 != s and not (len(s2) == 11 and s2.startswith("1") and s2.isdigit()):
        return s
    return s2


def mask_phone(value):
    """138****1234 形态掩码；非 11 位手机号仅保留前 3 后 1。"""
    s = normalize_phone(value) or ""
    if len(s) == 11 and s.startswith("1"):
        return s[:3] + "****" + s[-4:]
    if len(s) >= 4:
        return s[:3] + "****" + s[-1:]
    return "****"


def mask_credit_code(value):
    s = normalize_text(value) or ""
    if len(s) <= 8:
        return s[:2] + "****" if s else ""
    return s[:6] + "****" + s[-2:]
