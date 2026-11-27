"""含税/不含税金额、税率解析与大小写互校（S5-DOC-013）。

设计要点（为什么这么做）：
- 金额一律以「分」存整数：所有运算先把十进制字符串交给 Decimal，
  再乘 100 四舍五入到整数分，全程不出现 float，避免二进制浮点误差。
- 大模型不参与数值处理：本模块只做确定性解析与规则校验，可被单测穷举。
- 中文大写按「节」（个/万/亿）解析，每节四位，兼容 零/整 与 圆/元 混写。
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

# 大写数字与单位表（虚构数据，无真实主体信息）
_DIGIT = {"零": 0, "壹": 1, "贰": 2, "叁": 3, "肆": 4,
          "伍": 5, "陆": 6, "柒": 7, "捌": 8, "玖": 9}
_UNIT = {"拾": 10, "佰": 100, "仟": 1000}
_SECTION = {"万": 10 ** 4, "亿": 10 ** 8}
_CURRENCY = "¥￥＄$"
_ALLOWED_RATE_BP = {0, 100, 300, 600, 900, 1300}  # 0/1/3/6/9/13%


def _to_fen(value: Decimal) -> int:
    """Decimal 元 → 整数分，四舍五入（银行家舍入不符合合同口径，故用 HALF_UP）。"""
    return int((value * 100).to_integral_value(rounding=ROUND_HALF_UP))


def parse_lower(text: str) -> Optional[int]:
    """解析小写金额写法 → 整数分。

    支持：千分位(,)、货币符号(¥￥$)、数量级(千/万)、可选 元/圆 结尾、负号。
    例：¥1,234.56 → 123456 分；12.5万 → 12500000 分（12.5万元）。
    """
    if not isinstance(text, str):
        return None
    s = text.strip()
    if not s:
        return None
    neg = s.startswith("-")
    s = s.lstrip("-").strip().lstrip(_CURRENCY).strip()
    s = s.replace(",", "").replace("，", "")
    if s.endswith("元") or s.endswith("圆"):
        s = s[:-1]
    mult = 1
    if s.endswith("万"):
        mult, s = 10 ** 4, s[:-1]
    elif s.endswith("千"):
        mult, s = 10 ** 3, s[:-1]
    try:
        fen = _to_fen(Decimal(s) * mult)
    except Exception:
        return None
    return -fen if neg else fen


def _cn_int(seg: str) -> int:
    """解析中文大写整数节（个/万/亿），如 壹拾贰万叁仟 → 123000。"""
    total = 0
    section = 0
    number = 0
    for ch in seg:
        if ch in _DIGIT:
            number = _DIGIT[ch]
        elif ch in _UNIT:
            if number == 0:       # 「拾伍」= 15，省略前导壹
                number = 1
            section += number * _UNIT[ch]
            number = 0
        elif ch in _SECTION:
            section += number
            total += section * _SECTION[ch]
            section = 0
            number = 0
    return total + section + number


def _cn_dec(seg: str) -> int:
    """解析大写小数节（角/分）→ 整数分。「整」无角分返回 0。"""
    fen = 0
    if "角" in seg:
        jiao = seg.split("角", 1)[0][-1:]
        if jiao in _DIGIT:
            fen += _DIGIT[jiao] * 10
    if "分" in seg:
        idx = seg.find("分")
        if idx > 0:
            before = seg[idx - 1]
            if before in _DIGIT:
                fen += _DIGIT[before]
    return fen


def parse_upper(text: str) -> Optional[int]:
    """解析中文大写金额 → 整数分。

    支持：壹至玖/拾佰仟/万亿/圆元角分整，兼容 零 与 圆元混写。
    例：壹佰贰拾叁圆肆角伍分 → 12345；壹万圆整 → 1000000。
    """
    if not isinstance(text, str):
        return None
    s = "".join(text.split())  # 去空白
    if not s:
        return None
    yuan = -1
    for ch in ("圆", "元"):
        pos = s.find(ch)
        if pos >= 0:
            yuan = pos if yuan < 0 else min(yuan, pos)
    if yuan >= 0:
        int_seg, dec_seg = s[:yuan], s[yuan + 1:]
    else:
        # 无圆/元时：含角/分则整体是小数节（如「玖角捌分」=98分，角前数字属角、非整数）；
        # 否则整体是整数元（如「壹佰贰拾」=120元）。
        if "角" in s or "分" in s:
            int_seg, dec_seg = "", s
        else:
            int_seg, dec_seg = s, ""
    if not int_seg and not dec_seg:
        return None
    return _cn_int(int_seg) * 100 + _cn_dec(dec_seg)


def parse_rate(text: str) -> Optional[int]:
    """解析税率 → 基点(bp)，如 13% → 1300、6% → 600。"""
    if not isinstance(text, str):
        return None
    s = text.strip().replace("％", "%").replace("%", "")
    try:
        return int((Decimal(s) * 100).to_integral_value(rounding=ROUND_HALF_UP))
    except Exception:
        return None


def check_case(lower_fen: Optional[int], upper_fen: Optional[int]) -> bool:
    """规则1：小写与大写同时存在必须一致。缺任一方视为无需比对（通过）。"""
    if lower_fen is None or upper_fen is None:
        return True
    return lower_fen == upper_fen


def check_tax(with_tax: Optional[int], without_tax: Optional[int],
              rate_bp: Optional[int]) -> Optional[bool]:
    """规则2：含税 = 不含税 ×(1+税率)，四舍五入到分，容差 ±1 分。

    三项缺一返回 None（规则3：不自动推算）。仅三项齐全时给 True/False。
    """
    if with_tax is None or without_tax is None or rate_bp is None:
        return None
    expected = Decimal(without_tax) * (Decimal(1) + Decimal(rate_bp) / Decimal(10000))
    expected_fen = int(expected.to_integral_value(rounding=ROUND_HALF_UP))
    return abs(expected_fen - with_tax) <= 1


def is_unusual_rate(rate_bp: Optional[int]) -> bool:
    """规则4：税率不在 0/1/3/6/9/13% 白名单 → 需人工确认。"""
    return rate_bp is not None and rate_bp not in _ALLOWED_RATE_BP


def _after_anchor(seg: str, anchors: tuple) -> str:
    """取锚点词之后的片段（冒号、括号后的金额部分），供金额解析。"""
    for a in anchors:
        if a in seg:
            rest = seg.split(a, 1)[1]
            for sep in ("：", ":", "（", "("):
                if sep in rest:
                    rest = rest.split(sep, 1)[1]
            return rest.strip()
    return ""


def extract(text: str) -> dict:
    """从条款文本按锚点词抽取三项 + 大小写两种写法，并出校验标记。

    返回 dict 键：amount_with_tax_fen / amount_without_tax_fen / tax_rate_bp /
    flags（列表）。大模型不参与数值处理，本函数只做定位与确定性解析。
    """
    anchors_tax_in = ("价税合计", "合同总金额（含税）", "含税总价")
    anchors_tax_out = ("不含税金额",)
    anchors_rate = ("税率", "增值税")
    result = {"amount_with_tax_fen": None, "amount_without_tax_fen": None,
              "tax_rate_bp": None, "flags": []}

    with_tax_upper = None
    for line in text.splitlines():
        seg = line.strip()
        if not seg:
            continue
        if any(a in seg for a in anchors_tax_in):
            frag = _after_anchor(seg, anchors_tax_in)
            result["amount_with_tax_fen"] = parse_lower(frag)
        elif any(a in seg for a in anchors_tax_out):
            frag = _after_anchor(seg, anchors_tax_out)
            result["amount_without_tax_fen"] = parse_lower(frag)
        elif any(a in seg for a in anchors_rate) and ("%" in seg or "％" in seg):
            result["tax_rate_bp"] = parse_rate(seg)
        elif any(c in seg for c in _DIGIT) and ("圆" in seg or "元" in seg):
            # 独立成行的大写金额行：视为含税金额的大写写法（供规则1互校）
            with_tax_upper = parse_upper(seg)

    # 规则1：同一金额大小写同时出现须一致
    if not check_case(result["amount_with_tax_fen"], with_tax_upper):
        result["flags"].append("amount_case_mismatch")
    # 规则2/3：三项齐全才校验，缺项不推算
    tax_ok = check_tax(result["amount_with_tax_fen"],
                       result["amount_without_tax_fen"], result["tax_rate_bp"])
    if tax_ok is False:
        result["flags"].append("tax_inconsistent")
    if tax_ok is None:
        result["flags"].append("needs_manual_fill")
    # 规则4
    if is_unusual_rate(result["tax_rate_bp"]):
        result["flags"].append("tax_rate_unusual")
    return result
