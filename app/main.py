"""FastAPI 应用：内部入队接口、状态迁移、生效内容读取。

- POST /api/review/drafts                服务凭证鉴权入队（幂等：同 gw_request_id 返回已有草稿）
- POST /api/review/drafts/{id}/transition 生效/驳回/过期（同事务写 outbox）
- GET  /api/review/drafts/{id}/effective-content  读取生效内容（非 effective 返回 409）
"""
from fastapi import Depends, FastAPI, HTTPException, Response, status

from .auth import require_service_key
from .db import SessionLocal, engine, get_session
from .models import Base
from .schemas import DraftCreateRequest, DraftOut, EffectiveContentOut, TransitionOut
from .service import (
    create_draft,
    find_by_gw_request_id,
    get_effective_content,
    transition_draft,
)
from .validator import SchemaValidationError, validate_ai_content

app = FastAPI(title="S5-GW-027 草稿入队 / 幂等去重 / outbox 生效事件", version="1.0.0")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


def _draft_out(draft) -> DraftOut:
    return DraftOut(
        draft_id=draft.id,
        status=draft.status,
        final_level=draft.final_level,
        requested_level=draft.requested_level,
        schema_id=draft.schema_id,
        schema_version=draft.schema_version,
        gw_request_id=draft.gw_request_id,
        feature_code=draft.feature_code,
        source_type=draft.source_type,
        source_id=draft.source_id,
        created_at=draft.created_at.isoformat(),
    )


@app.post("/api/review/drafts", response_model=DraftOut)
def enqueue_draft(
    req: DraftCreateRequest,
    response: Response,
    service_key_id: str = Depends(require_service_key),
):
    session = SessionLocal()
    try:
        existing = find_by_gw_request_id(session, req.gw_request_id)
        if existing is not None:
            # 幂等：同一 gw_request_id 重复提交返回已有草稿（draft_id 相同）
            return _draft_out(existing)

        # 入队前按登记 schema 校验 ai_content，不合格 422 且不落库
        try:
            validate_ai_content(req.schema_id, req.schema_version, req.ai_content)
        except SchemaValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc

        draft = create_draft(session, {**req.model_dump(), "service_key_id": service_key_id})
        session.commit()
        session.refresh(draft)
        response.status_code = status.HTTP_201_CREATED
        return _draft_out(draft)
    finally:
        session.close()


@app.post("/api/review/drafts/{draft_id}/transition", response_model=TransitionOut)
def transition(
    draft_id: str,
    req: dict,
    service_key_id: str = Depends(require_service_key),
):
    action = req.get("action")
    if action not in {"effective", "rejected", "expired"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="action must be one of effective/rejected/expired",
        )
    session = SessionLocal()
    try:
        from .models import Draft  # 局部导入避免循环

        draft = session.get(Draft, draft_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="draft not found")
        try:
            event = transition_draft(session, draft, action)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc
        session.commit()
        return TransitionOut(
            draft_id=draft.id, status=draft.status, event_id=event.id,
            event_type=event.event_type,
        )
    finally:
        session.close()


@app.get("/api/review/drafts/{draft_id}/effective-content", response_model=EffectiveContentOut)
def effective_content(draft_id: str):
    session = SessionLocal()
    try:
        data = get_effective_content(session, draft_id)
        if data is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="draft not found or not in effective status",
            )
        return data
    finally:
        session.close()
