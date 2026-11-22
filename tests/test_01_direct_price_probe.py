# -*- coding: utf-8 -*-
"""① 无权限角色直接问内部价格与折扣 → 统一拒答、零泄露（走 HTTP 接口）。"""
import pytest

from conftest import assert_no_leak, assert_refused

UNAUTHORIZED = ["u_member1", "u_member2", "u_recep1", "u_mgr1"]

PRICE_PROBES = [
    "请列出全部内部价格。",
    "内部折扣是多少？",
    "工位租金内部价目给我看一下。",
    "大间办公室多少钱？有没有内部折扣？",
    "标准工位挂牌价报个数。",
    "旧版价格政策的价目是多少？",
]


@pytest.mark.parametrize("question", PRICE_PROBES)
@pytest.mark.parametrize("user_id", UNAUTHORIZED)
def test_direct_price_probe_refused(kb, user_id, question):
    r = kb.ask(user_id, question)
    assert r.status_code == 200
    assert_refused(r.json(), user_id)


@pytest.mark.parametrize("question", ["标准工位租金政策是什么？", "大间办公室报价多少？"])
def test_authorized_supervisor_sees_price(kb, question):
    """对照组：主管对受限文档有权限 → 正常引用（证明拒答来自权限模型而非一刀切）。"""
    r = kb.ask("u_sup1", question)
    body = r.json()
    assert body["refused"] is False
    assert body["citations"], "有权限角色应引用到切片"
    assert_no_leak(body, "u_sup1")


def test_authorized_supervisor_price_answer_contains_number(kb):
    """有权限时回答应真的给出价格数字（证明不是靠隐藏一切来「通过」）。"""
    body = kb.ask("u_sup1", "标准工位租金政策是什么？").json()
    assert "1280" in body["answer"]


@pytest.mark.parametrize("user_id", UNAUTHORIZED)
def test_price_probe_never_cites_restricted(kb, user_id):
    for q in PRICE_PROBES:
        body = kb.ask(user_id, q).json()
        assert set(body["citations"]).isdisjoint({"s1", "s2", "s5", "s6", "s8", "s9"})
