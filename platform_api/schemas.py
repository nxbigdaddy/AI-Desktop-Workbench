from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserProfile(ORMModel):
    id: str
    wecom_userid: str
    display_name: str
    department_code: str
    is_admin: bool


class WeComTransactionCreate(BaseModel):
    device_id: str = Field(min_length=3, max_length=128)


class WeComTransactionCreated(BaseModel):
    transaction_id: str
    poll_secret: str
    qr_url: str
    expires_at: datetime
    mode: Literal["fake", "wecom"]


class WeComTransactionPoll(BaseModel):
    transaction_id: str
    poll_secret: str = Field(min_length=20, max_length=256)


class WeComTransactionStatus(BaseModel):
    transaction_id: str
    status: Literal["pending", "approved", "expired", "exchanged", "rejected"]
    expires_at: datetime
    exchange_code: str | None = None
    user: UserProfile | None = None


class FakeWeComApproval(BaseModel):
    wecom_userid: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=128)
    department_code: str = Field(default="", max_length=128)
    is_admin: bool = False


class TokenExchangeRequest(BaseModel):
    transaction_id: str
    exchange_code: str = Field(min_length=20, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    session_id: str
    idle_timeout_days: int
    user: UserProfile


class ConversationCreate(BaseModel):
    title: str = Field(default="新对话", min_length=1, max_length=256)


class ConversationView(ORMModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)
    logical_model: str = Field(default="general-fast", min_length=1, max_length=128)
    idempotency_key: str | None = Field(default=None, max_length=128)


class UsageView(BaseModel):
    request_id: str
    logical_model: str
    actual_model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    source: str


class ChatResponse(BaseModel):
    conversation_id: str
    user_message_id: str
    assistant_message_id: str
    content: str
    usage: UsageView
    applied_prompts: list[str]


class UsageSummary(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_count: int
    source_breakdown: dict[str, int]


class PromptCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    purpose: str = Field(min_length=1, max_length=256)
    version: int = Field(default=1, ge=1)
    system_prompt: str = Field(min_length=1, max_length=100_000)
    variables_schema: dict[str, Any] = Field(default_factory=dict)
    allowed_tools: list[str] = Field(default_factory=list)
    status: Literal["draft", "published"] = "draft"
    expires_at: datetime | None = None


class PromptAssignmentCreate(BaseModel):
    subject_type: Literal["all", "user", "department"]
    subject_id: str = Field(default="", max_length=128)
    required: bool = True


class PromptView(ORMModel):
    id: str
    name: str
    purpose: str
    version: int
    system_prompt: str
    variables_schema: dict[str, Any]
    allowed_tools: list[str]
    status: str
    expires_at: datetime | None
    required: bool = True


class AuditEventView(ORMModel):
    id: str
    actor_user_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    result: str
    trace_id: str
    metadata_json: dict[str, Any]
    occurred_at: datetime


class ErrorBody(BaseModel):
    code: str
    message: str

