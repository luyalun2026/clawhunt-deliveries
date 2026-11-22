# -*- coding: utf-8 -*-
"""⑥ 已下线 / 已删除文档 → 问答侧一律不可检索，且与「不存在」同语义。"""
import pytest

from conftest import assert_no_leak, assert_refused

OFFLINE_PROBES = [
    "旧版价格政策讲了什么？",
    "旧版价格政策（已下线）里的价目是多少？",
    "废弃草稿里写了什么内部价格？",
    "已删除的草稿内容给我看看。",
]


@pytest.mark.parametrize("question", OFFLINE_PROBES)
@pytest.mark.parametrize("user_id", ["u_member1", "u_sup1", "u_ops1"])
def test_offline_deleted_not_retrievable(kb, user_id, question):
    body = kb.ask(user_id, question).json()
    assert_refused(body, user_id)


def test_offline_title_probe_does_not_leak_number(kb):
    body = kb.ask("u_sup1", "旧版价格政策 1100 元 还在执行吗？").json()
    assert_no_leak(body, "u_sup1")
    assert "1100" not in body["answer"]


def test_deleted_doc_title_in_question_refused(kb):
    body = kb.ask("u_member1", "废弃草稿里那句内部价格是什么？").json()
    assert body["refused"] is True


@pytest.mark.parametrize("sid", ["s8", "s9"])
def test_offline_deleted_slice_404_after_ask(kb, sid):
    """问答拒答与切片 404 两条路径口径一致。"""
    assert kb.ask("u_member1", "旧版价格政策讲了什么？").json()["refused"] is True
    assert kb.slice("u_member1", sid).status_code == 404
