"""S5-GW-027 验收标准（AC）与核心行为测试。"""
from sqlalchemy.orm import Session, sessionmaker

from app.db import engine
from app.delivery import deliver_pending
from app.models import Draft, DraftEvent
from app.service import transition_draft
from tests.conftest import HEADERS, make_payload


def _enqueue(client, **overrides):
    return client.post(
        "/api/review/drafts", json=make_payload(**overrides), headers=HEADERS
    )


# ---------- AC1：同一 gw_request_id 幂等，draft_id 相同 ----------
def test_ac1_idempotent_same_gw_request_id(client):
    r1 = _enqueue(client, gw_request_id="gw-ac1")
    assert r1.status_code == 201, r1.text
    r2 = _enqueue(client, gw_request_id="gw-ac1")
    assert r2.status_code == 200, r2.text
    assert r1.json()["draft_id"] == r2.json()["draft_id"]

    with Session(bind=engine) as s:
        drafts = s.query(Draft).filter(Draft.gw_request_id == "gw-ac1").all()
        assert len(drafts) == 1


# ---------- AC2：ai_content 不符合 schema -> 422 且不落库 ----------
def test_ac2_invalid_ai_content_422_not_persisted(client):
    bad_content = {"summary": "缺 keywords 与 confidence_score"}
    r = _enqueue(client, gw_request_id="gw-ac2", ai_content=bad_content)
    assert r.status_code == 422
    assert "failed schema" in r.json()["detail"]

    with Session(bind=engine) as s:
        assert (
            s.query(Draft).filter(Draft.gw_request_id == "gw-ac2").count() == 0
        )


def test_ac2b_unknown_schema_also_422(client):
    r = _enqueue(client, gw_request_id="gw-ac2b", schema_id="no.such.schema")
    assert r.status_code == 422
    assert "unknown schema" in r.json()["detail"]


# ---------- AC3：草稿生效 + outbox 写入同一事务，回滚后两者均不存在 ----------
def test_ac3_rollback_discards_both_status_and_event(client):
    draft_id = _enqueue(client, gw_request_id="gw-ac3").json()["draft_id"]

    # 模拟同一事务：service 层只 flush 不 commit，外部事务回滚即可整体丢弃
    conn = engine.connect()
    trans = conn.begin()
    try:
        tx_session = Session(bind=conn, join_transaction_mode="create_savepoint")
        draft = tx_session.get(Draft, draft_id)
        event = transition_draft(tx_session, draft, "effective")
        tx_session.flush()
        # 事务内：状态已生效且 outbox 已写入
        assert tx_session.get(Draft, draft_id).status == "effective"
        assert (
            tx_session.query(DraftEvent).filter_by(draft_id=draft_id).count() == 1
        )
        assert event.event_type == "ai.draft.effective"
    finally:
        trans.rollback()
        conn.close()

    # 回滚后：状态与事件都不存在
    with Session(bind=engine) as s:
        assert s.get(Draft, draft_id).status == "pending_review"
        assert s.query(DraftEvent).filter_by(draft_id=draft_id).count() == 0


def test_ac3b_commit_persists_both(client):
    draft_id = _enqueue(client, gw_request_id="gw-ac3b").json()["draft_id"]
    with Session(bind=engine) as s:
        draft = s.get(Draft, draft_id)
        transition_draft(s, draft, "effective")
        s.commit()
    with Session(bind=engine) as s:
        assert s.get(Draft, draft_id).status == "effective"
        assert s.query(DraftEvent).filter_by(draft_id=draft_id).count() == 1


# ---------- AC4：未生效草稿读取 effective-content 返回 409 ----------
def test_ac4_non_effective_content_409(client):
    draft_id = _enqueue(client, gw_request_id="gw-ac4").json()["draft_id"]
    r = client.get(f"/api/review/drafts/{draft_id}/effective-content")
    assert r.status_code == 409

    # 生效后才能读取
    with Session(bind=engine) as s:
        transition_draft(s, s.get(Draft, draft_id), "effective")
        s.commit()
    r2 = client.get(f"/api/review/drafts/{draft_id}/effective-content")
    assert r2.status_code == 200
    body = r2.json()
    assert body["draft_id"] == draft_id
    assert body["content"]["summary"].startswith("某会员企业")


def test_ac4b_unknown_draft_409(client):
    assert (
        client.get("/api/review/drafts/does-not-exist/effective-content").status_code
        == 409
    )


# ---------- 服务凭证鉴权 ----------
def test_requires_service_key(client):
    r = client.post("/api/review/drafts", json=make_payload(gw_request_id="gw-auth"))
    assert r.status_code in (401, 403, 422)
    r2 = client.post(
        "/api/review/drafts",
        json=make_payload(gw_request_id="gw-auth"),
        headers={"X-Service-Key": "wrong-key"},
    )
    assert r2.status_code == 401


# ---------- 最终级别由状态机规则决定并在响应中返回 ----------
def test_final_level_downgrade_rule(client):
    r = _enqueue(client, gw_request_id="gw-level-ok", requested_level="standard")
    assert r.json()["final_level"] == "L2"  # score 0.9 >= 0.6，保留 standard(L2)

    low_score = {"summary": "s", "keywords": ["k"], "confidence_score": 0.5}
    r2 = _enqueue(
        client, gw_request_id="gw-level-low", requested_level="standard",
        ai_content=low_score,
    )
    assert r2.json()["final_level"] == "L1"  # 0.5 < 0.6，降一级


# ---------- 状态迁移终态不可重复迁移 ----------
def test_transition_twice_conflict(client):
    draft_id = _enqueue(client, gw_request_id="gw-twice").json()["draft_id"]
    r1 = client.post(
        f"/api/review/drafts/{draft_id}/transition",
        json={"action": "rejected"}, headers=HEADERS,
    )
    assert r1.status_code == 200
    r2 = client.post(
        f"/api/review/drafts/{draft_id}/transition",
        json={"action": "expired"}, headers=HEADERS,
    )
    assert r2.status_code == 409


# ---------- outbox 投递任务：至少一次、2xx 才标记送达 ----------
def test_delivery_at_least_once(client):
    draft_id = _enqueue(client, gw_request_id="gw-dlv").json()["draft_id"]
    with Session(bind=engine) as s:
        transition_draft(s, s.get(Draft, draft_id), "effective")
        s.commit()

    delivered_bodies = []

    def poster(url, body):
        delivered_bodies.append(body)
        return True

    with Session(bind=engine) as s:
        n = deliver_pending(s, poster=poster, url="http://subscriber.test/hook")
        assert n >= 1
        ev = s.query(DraftEvent).filter_by(draft_id=draft_id).one()
        assert ev.delivered_at is not None

    bodies_for_draft = [b for b in delivered_bodies if b["draft_id"] == draft_id]
    assert len(bodies_for_draft) == 1
    assert bodies_for_draft[0]["event_type"] == "ai.draft.effective"

    # 已标记送达的事件不再重投（订阅方仍可按 draft_id 幂等去重）
    with Session(bind=engine) as s:
        assert deliver_pending(s, poster=poster, url="http://subscriber.test/hook") == 0


def test_delivery_failure_keeps_event_pending(client):
    draft_id = _enqueue(client, gw_request_id="gw-dlv-fail").json()["draft_id"]
    with Session(bind=engine) as s:
        transition_draft(s, s.get(Draft, draft_id), "rejected")
        s.commit()

    def failing_poster(url, body):
        return False

    with Session(bind=engine) as s:
        assert deliver_pending(s, poster=failing_poster, url="http://x.test") == 0
        ev = s.query(DraftEvent).filter_by(draft_id=draft_id).one()
        assert ev.delivered_at is None
        assert ev.delivery_attempts == 1
