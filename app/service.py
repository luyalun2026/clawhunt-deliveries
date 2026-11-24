"""业务服务层：入队（幂等）、状态迁移（同事务写 outbox）、生效内容读取。

约定：本层只 flush 不 commit，由调用方（API 层 / 测试）控制事务边界——
这保证「草稿生效 + outbox 写入」天然处于同一事务，可整体回滚。
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Draft, DraftEvent, new_id, utcnow
from .state_machine import EVENT_TYPE_BY_ACTION, compute_final_level


def find_by_gw_request_id(session: Session, gw_request_id: str) -> Draft | None:
    return session.execute(
        select(Draft).where(Draft.gw_request_id == gw_request_id)
    ).scalar_one_or_none()


def create_draft(session: Session, payload: dict) -> Draft:
    """入队：校验由接口层完成，这里负责最终级别计算与落库（flush，不 commit）。"""
    ai_content = payload["ai_content"]
    draft = Draft(
        id=new_id(),
        org_id=payload.get("org_id", ""),
        site_id=payload.get("site_id", ""),
        feature_code=payload["feature_code"],
        source_type=payload["source_type"],
        source_id=payload["source_id"],
        title=payload["title"],
        ai_content=ai_content,
        schema_id=payload["schema_id"],
        schema_version=payload["schema_version"],
        gw_request_id=payload["gw_request_id"],
        drafter_id=payload["drafter_id"],
        requested_level=payload["requested_level"],
        final_level=compute_final_level(payload["requested_level"], ai_content),
        status="pending_review",
        created_by=payload.get("service_key_id", "service"),
    )
    session.add(draft)
    session.flush()
    return draft


def transition_draft(session: Session, draft: Draft, action: str) -> DraftEvent:
    """状态迁移：草稿状态变更与 outbox 事件写入在同一事务（同一 session）内完成。

    action ∈ {effective, rejected, expired}。
    """
    event_type = EVENT_TYPE_BY_ACTION[action]
    if draft.status != "pending_review":
        raise ValueError(f"draft {draft.id} not in pending_review (status={draft.status})")

    draft.status = action
    draft.updated_at = utcnow()
    if action == "effective":
        draft.effective_at = utcnow()

    event = DraftEvent(
        id=new_id(),
        event_type=event_type,
        draft_id=draft.id,
        feature_code=draft.feature_code,
        source_type=draft.source_type,
        source_id=draft.source_id,
        payload={
            "draft_id": draft.id,
            "feature_code": draft.feature_code,
            "source_type": draft.source_type,
            "source_id": draft.source_id,
            "status": draft.status,
            "final_level": draft.final_level,
            "occurred_at": utcnow().isoformat(),
        },
    )
    session.add(event)
    session.flush()
    return event


def get_effective_content(session: Session, draft_id: str) -> dict | None:
    """仅 effective 状态返回生效内容；其余状态由接口层转 409。"""
    draft = session.get(Draft, draft_id)
    if draft is None or draft.deleted_at is not None:
        return None
    if draft.status != "effective":
        return None
    return {
        "draft_id": draft.id,
        "feature_code": draft.feature_code,
        "source_type": draft.source_type,
        "source_id": draft.source_id,
        "final_level": draft.final_level,
        "content": draft.ai_content,
        "effective_at": draft.effective_at.isoformat() if draft.effective_at else None,
    }
