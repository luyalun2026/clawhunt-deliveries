"""API 请求/响应模型。"""
from typing import Literal

from pydantic import BaseModel, Field


class DraftCreateRequest(BaseModel):
    feature_code: str = Field(min_length=1, max_length=64)
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    ai_content: object
    schema_id: str = Field(min_length=1, max_length=64)
    schema_version: str = Field(min_length=1, max_length=32)
    gw_request_id: str = Field(min_length=1, max_length=128)
    drafter_id: str = Field(min_length=1, max_length=64)
    requested_level: Literal["strict", "standard", "draft"]
    org_id: str = Field(default="", max_length=64)
    site_id: str = Field(default="", max_length=64)


class TransitionRequest(BaseModel):
    action: Literal["effective", "rejected", "expired"]


class DraftOut(BaseModel):
    draft_id: str
    status: str
    final_level: str
    requested_level: str
    schema_id: str
    schema_version: str
    gw_request_id: str
    feature_code: str
    source_type: str
    source_id: str
    created_at: str


class TransitionOut(BaseModel):
    draft_id: str
    status: str
    event_id: str
    event_type: str


class EffectiveContentOut(BaseModel):
    draft_id: str
    feature_code: str
    source_type: str
    source_id: str
    final_level: str
    content: object
    effective_at: str
