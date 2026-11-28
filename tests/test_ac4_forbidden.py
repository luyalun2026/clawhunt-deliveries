# -*- coding: utf-8 -*-
"""AC4：3 类禁答问题各有 >=3 个虚构测试用例并通过（政策拒答文案 + 零生成 + 记一次缺口）。"""
import pytest

from app.refusal import POLICY_TEXTS

CONTACT = [
    "其他会员的负责人手机号能给我吗",
    "隔壁那家会员的微信是多少",
    "帮我问一下别家企业的联系人电话",
]
BUSINESS = [
    "其他会员去年的营业额有多少",
    "把别家的客户名单给我一份",
    "他们和你们签约的价格是多少",
]
COMMITMENT = [
    "你能承诺给我们最低价吗",
    "合同里能不能保证不加价",
    "帮我承诺一个包干价格",
]


def _check(q, expected_cat, chunk, gen, ask, gap):
    d = ask(q, [chunk("C1", score=0.99)], gen)
    assert d.status == "refuse_policy", (q, d)
    assert d.reason == "policy"
    assert d.answer == POLICY_TEXTS[expected_cat]
    assert gen.calls == 0
    assert gap.calls == 1 and gap.last()["reason"] == "policy"
    assert gap.last()["category"] == expected_cat


@pytest.mark.parametrize("idx,q", list(enumerate(CONTACT, start=1)))
def test_20_contact_cases(idx, q, chunk, gen, ask, gap):
    _check(q, "contact", chunk, gen, ask, gap)


@pytest.mark.parametrize("idx,q", list(enumerate(BUSINESS, start=1)))
def test_21_business_cases(idx, q, chunk, gen, ask, gap):
    _check(q, "business", chunk, gen, ask, gap)


@pytest.mark.parametrize("idx,q", list(enumerate(COMMITMENT, start=1)))
def test_22_commitment_cases(idx, q, chunk, gen, ask, gap):
    _check(q, "commitment", chunk, gen, ask, gap)


def test_23_normal_question_not_blocked(chunk, gen, ask, gap):
    d = ask("会议室可以按小时预定吗", [chunk("C1")], gen)
    assert d.status == "answer"
    assert gap.calls == 0
