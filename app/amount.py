"""含税/不含税金额与税率解析、大小写互校（S5-DOC-013）。

统一技术约定：金额一律 Decimal 解析后转「分」整数，禁止 float 参与金额运算。
- 小写金额：千分位、货币符号、数量级单位（千/万）。
- 中文大写金额：壹至玖、拾佰仟、万亿、圆元角分整。
- 税率以 basis point（bp）存整数：1300 = 13%。
所有数值处理为纯函数；AI/大模型不参与任何金额计算。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

# ---- 中文大写数字表 ----
_CN_NUM = {
    "零": 0, "〇": 0, "壹": 1, "贰": 2, "叁": 3, "肆": 4,
    "伍": 5, "陆": 6, "柒": 7, "捌": 8, "玖": 9,
}
_CN_UNIT_SMALL = {"拾": 10, "佰": 100, "仟": 1000}
_CN_UNIT_BIG = {"万": 10 ** 4, "亿": 10 ** 8}

# 锚点词（按优先级排列，含同义写法）
ANCHOR_WITH_TAX = ["价税合计", "合同总金额（含税）", "合同总金额(含税)", "含税总价", "含税金额", "含税"]
ANCHOR_WITHOUT_TAX = ["不含税金额", "不含税"]
ANCHOR_TAX_RATE = ["税率", "增值税"]

ALLOWED_RATES_BP = {0, 100, 300, 600, 900, 1300}  # 0/1/3/6/9/13%


def _to_fen(amount: Decimal) -> int:
    """Decimal 元金额 -> 分整数，四舍五入到分。唯一出口，全程无 float。"""
    return int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_lower_amount(text: str) -> Optional[int]:
    """解析小写金额为分整数。支持千分位、¥/￥、千/万数量级、小数。无匹配返回 None。"""
    if not text:
        return None
    s = str(text).strip().replace(",", "").replace("，", "")
    s = s.replace("¥", "").replace("￥", "").replace("$", "").strip()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(万|千)?", s)
    if not m:
        return None
    num = Decimal(m.group(1))
    suffix = m.group(2)
    if suffix == "万":
        num *= Decimal("10000")
    elif suffix == "千":
        num *= Decimal("1000")
    return _to_fen(num)


def parse_upper_amount(text: str) -> Optional[int]:
    """解析中文大写金额为分整数。支持壹至玖、拾佰仟、万亿、圆元角分整。"""
    if not text:
        return None
    s = str(text).strip()
    s = s.replace("人民币", "").replace("整", "").strip()
    # 分/角部分
    fen = 0
    mf = re.search(r"([零〇壹贰叁肆伍陆柒捌玖])分", s)
    if mf:
        fen = _CN_NUM[mf.group(1)]
        s = s[:mf.start()] + s[mf.end():]
    jiao = 0
    mj = re.search(r"([零〇壹贰叁肆伍陆柒捌玖])角", s)
    if mj:
        jiao = _CN_NUM[mj.group(1)] * 10
        s = s[:mj.start()] + s[mj.end():]
    # 元/圆 分隔整数部分
    s = re.split(r"[圆元]", s)[0]
    if not s:
        return fen + jiao
    total = 0
    section = 0
    digit = 0
    for ch in s:
        if ch in _CN_NUM:
            digit = _CN_NUM[ch]
        elif ch in _CN_UNIT_SMALL:
            unit = _CN_UNIT_SMALL[ch]
            section += (digit if digit else 1) * unit  # "拾"前省略"壹"
            digit = 0
        elif ch in _CN_UNIT_BIG:
            section += digit
            total += section * _CN_UNIT_BIG[ch]
            section = 0
            digit = 0
    return _to_fen(Decimal(total + section + digit)) + fen + jiao


def parse_tax_rate(text: str) -> Optional[int]:
    """解析税率为 bp 整数。'13%' -> 1300；'6%' -> 600。"""
    if not text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", str(text))
    if not m:
        return None
    pct = Decimal(m.group(1))
    return int((pct * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _find_after_anchor(text: str, anchors: List[str]) -> Optional[str]:
    """取锚点词之后的一段文本（到句号/分号/换行为止）。"""
    for a in anchors:
        idx = text.find(a)
        if idx < 0:
            continue
        seg = text[idx + len(a): idx + len(a) + 40]
        seg = re.split(r"[。；;\n]", seg)[0]
        return seg
    return None


def _parse_any_amount(seg: str) -> Optional[int]:
    """段落内优先取大写金额，其次小写金额。"""
    if not seg:
        return None
    m_upper = re.search(r"[零〇壹贰叁肆伍陆柒捌玖拾佰仟万亿圆元角分整]{2,}", seg)
    if m_upper:
        v = parse_upper_amount(m_upper.group(0))
        if v is not None:
            return v
    return parse_lower_amount(seg)


@dataclass
class AmountResult:
    amount_with_tax_fen: Optional[int] = None
    amount_without_tax_fen: Optional[int] = None
    tax_rate_bp: Optional[int] = None
    amount_case_mismatch: bool = False
    tax_inconsistent: bool = False
    tax_rate_unusual: bool = False
    need_human_review: bool = False
    notes: List[str] = field(default_factory=list)

    def public(self) -> Dict:
        return {
            "amount_with_tax_fen": self.amount_with_tax_fen,
            "amount_without_tax_fen": self.amount_without_tax_fen,
            "tax_rate_bp": self.tax_rate_bp,
            "amount_case_mismatch": self.amount_case_mismatch,
            "tax_inconsistent": self.tax_inconsistent,
            "tax_rate_unusual": self.tax_rate_unusual,
            "need_human_review": self.need_human_review,
            "notes": list(self.notes),
        }


def check_and_reconcile(text: str, fixtures: Optional[List[Dict]] = None) -> AmountResult:
    """从条款/表格文本抽取三项数值并执行四条校验规则（程序执行，AI 不参与）。

    fixtures: 可选夹具列表，每项含 anchor / lower / upper / expect_fen，用于大小写互校。
    """
    res = AmountResult()

    # 抽取三项
    seg_tax = _find_after_anchor(text, ANCHOR_WITH_TAX)
    seg_no = _find_after_anchor(text, ANCHOR_WITHOUT_TAX)
    seg_rate = _find_after_anchor(text, ANCHOR_TAX_RATE)
    res.amount_with_tax_fen = _parse_any_amount(seg_tax)
    res.amount_without_tax_fen = _parse_any_amount(seg_no)
    res.tax_rate_bp = parse_tax_rate(seg_rate) if seg_rate else None

    # 规则 1：同一金额大小写同时存在须一致，否则 amount_case_mismatch + 强制人工核对
    for fx in (fixtures or []):
        lower = parse_lower_amount(fx.get("lower") or "")
        upper = parse_upper_amount(fx.get("upper") or "")
        if lower is not None and upper is not None and lower != upper:
            res.amount_case_mismatch = True
            res.need_human_review = True
            res.notes.append(f"大小写不一致: {fx.get('lower')} vs {fx.get('upper')}")

    # 规则 4：税率白名单
    if res.tax_rate_bp is not None and res.tax_rate_bp not in ALLOWED_RATES_BP:
        res.tax_rate_unusual = True
        res.need_human_review = True
        res.notes.append(f"异常税率 {res.tax_rate_bp}bp")

    # 规则 3：只出现两项时不自动推算第三项，留空并提示补录
    present = [x is not None for x in (
        res.amount_with_tax_fen, res.amount_without_tax_fen, res.tax_rate_bp)]
    if sum(present) == 2:
        res.need_human_review = True
        res.notes.append("仅两项，第三项留空待补录，不推算")

    # 规则 2：三项齐全校验 含税 = 不含税 × (1+税率)，容差 ±1 分
    if all(present):
        rate = Decimal(res.tax_rate_bp) / Decimal("10000")
        expect = _to_fen(Decimal(res.amount_without_tax_fen) / Decimal("100") * (Decimal("1") + rate))
        if abs(expect - res.amount_with_tax_fen) > 1:
            res.tax_inconsistent = True
            res.need_human_review = True
            res.notes.append(
                f"含税不符: 实得 {res.amount_with_tax_fen} 分, 期望 {expect} 分")

    return res
