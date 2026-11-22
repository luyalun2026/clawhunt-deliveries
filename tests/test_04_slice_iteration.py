# -*- coding: utf-8 -*-
"""④⑤ 切片 id 遍历（IDOR）与 404 语义一致性：四种情形响应体完全相同。"""
import pytest

ALL_SLICES = ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9"]

# 角色 → 应可读取的切片（来自 corpus.json 的角色白名单 × active 状态）
VISIBLE = {
    "u_member1": {"s3", "s7"},
    "u_recep1": {"s3", "s4", "s7"},
    "u_mgr1": {"s3", "s7"},
    "u_ops1": {"s1", "s2", "s3", "s4", "s7"},
    "u_sup1": {"s1", "s2", "s3", "s4", "s5", "s6", "s7"},
}

GHOST = {
    "s8": "已下线文档的切片",
    "s9": "已删除文档的切片",
    "s_nope": "不存在的切片 id",
}


@pytest.mark.parametrize("user_id", list(VISIBLE))
def test_slice_matrix_matches_permission_model(kb, user_id):
    for sid in ALL_SLICES:
        r = kb.slice(user_id, sid)
        if sid in VISIBLE[user_id]:
            assert r.status_code == 200, "%s 应可读 %s" % (user_id, sid)
            assert r.json()["slice_id"] == sid
        else:
            assert r.status_code == 404, "%s 不应读到 %s" % (user_id, sid)


@pytest.mark.parametrize("sid", ["s1", "s2", "s5", "s6", "s8", "s9"])
def test_member_idor_blocked(kb, sid):
    body = kb.slice("u_member1", sid).json()
    assert body == {"error": "not_found", "detail": "resource not found"}


def test_404_body_identical_across_four_situations(kb):
    """无权限 / 不存在 / 已下线 / 已删除 → 同一 status + 同一 body。"""
    no_perm = kb.slice("u_member1", "s1")
    not_exist = kb.slice("u_member1", "s_nope")
    offline = kb.slice("u_member1", "s8")
    deleted = kb.slice("u_member1", "s9")
    for r in (no_perm, not_exist, offline, deleted):
        assert r.status_code == 404
        assert r.json() == not_exist.json()
        assert r.headers["content-type"].startswith("application/json")


def test_404_identical_even_for_authorized_role_on_offline(kb):
    """主管对 D6 有角色权限但文档已下线 → 仍与「不存在」完全一致。"""
    assert kb.slice("u_sup1", "s8").json() == kb.slice("u_sup1", "s_nope").json()
    assert kb.slice("u_sup1", "s9").json() == kb.slice("u_sup1", "s_nope").json()


@pytest.mark.parametrize("sid", ["s3", "s7"])
def test_visible_slice_returns_text(kb, sid):
    body = kb.slice("u_member1", sid).json()
    assert body["text"], "可见切片应返回非空正文"
    assert body["doc_id"].startswith("D")
