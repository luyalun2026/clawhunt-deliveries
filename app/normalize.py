# -*- coding: utf-8 -*-
"""归一化与哈希：企业名、统一社会信用代码、手机号。"""
from __future__ import annotations

import hashlib
import os
import re
import unicodedata

# 只剥离一次法律形式后缀，避免过度归一把不同主体并成一家
_LEGAL_SUFFIXES = (
    "股份有限公司", "有限责任公司", "集团有限公司", "有限公司", "集团", "公司",
)


def normalize_name(name: str) -> str:
    """全角转半角、去括号内容、去空白与标点、统一小写、剥离法律形式后缀。"""
    text = unicodedata.normalize("NFKC", name or "").strip()
    text = re.sub(r"[（(][^）)]*[）)]", "", text)
    text = re.sub(r"[\s\u3000]+", "", text)
    text = re.sub(r"[·・.,，、。\-—_/\\'\"“”‘’]", "", text)
    text = text.lower()
    for suffix in _LEGAL_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    return text


def normalize_uscc(uscc: str | None) -> str | None:
    value = (uscc or "").strip().upper()
    return value or None


def normalize_phone(phone: str | None) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("86") and len(digits) == 13:
        digits = digits[2:]
    return digits


def phone_hash(phone: str | None, salt: str | None = None) -> str:
    salt = salt if salt is not None else os.environ.get("ATTRIBUTION_PHONE_SALT", "local-dev-salt")
    norm = normalize_phone(phone)
    return hashlib.sha256((salt + "|" + norm).encode("utf-8")).hexdigest()[:32]


def is_valid_phone(phone: str | None) -> bool:
    return re.fullmatch(r"1[3-9]\d{9}", normalize_phone(phone)) is not None


def is_plausible_uscc(uscc: str | None) -> bool:
    value = normalize_uscc(uscc)
    return bool(value) and re.fullmatch(r"[0-9A-HJ-NPQRTUWXY]{18}", value) is not None


def build_keys(uscc: str | None, name: str, phone: str | None,
               salt: str | None = None) -> list[tuple[str, str]]:
    """返回 [(key, key_type)]，顺序固定，便于断言。"""
    keys: list[tuple[str, str]] = []
    norm_uscc = normalize_uscc(uscc)
    if norm_uscc:
        keys.append(("uscc:" + norm_uscc, "uscc"))
    norm_name = normalize_name(name)
    if norm_name:
        keys.append(("name:" + norm_name, "name"))
    if normalize_phone(phone):
        keys.append(("phone:" + phone_hash(phone, salt), "phone"))
    return keys
