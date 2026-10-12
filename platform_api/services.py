from __future__ import annotations

import hashlib
import math
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .config import Settings
from .models import (
    AuditEvent,
    Conversation,
    Message,
    PromptAssignment,
    PromptPackage,
    UsageRecord,
    User,
    UserSession,
    WeComAuthTransaction,
    utc_now,
)
from .schemas import (
    ChatResponse,
    FakeWeComApproval,
    PromptAssignmentCreate,
    PromptCreate,
    PromptView,
    UsageSummary,
    UsageView,
)
from .wecom import WeComAPIError, WeComClient


class ServiceError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_secret() -> str:
    return secrets.token_urlsafe(36)


def new_trace_id() -> str:
    return uuid.uuid4().hex


def add_audit(
    session: Session,
    *,
    action: str,
    resource_type: str,
    result: str,
    actor_user_id: str | None = None,
    session_id: str | None = None,
    resource_id: str | None = None,
    trace_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_user_id=actor_user_id,
        session_id=session_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result,
        trace_id=trace_id or new_trace_id(),
        metadata_json=metadata or {},
    )
    session.add(event)
    return event


@dataclass(frozen=True, slots=True)
class Principal:
    user: User
    user_session: UserSession


class AuthService:
    def __init__(self, settings: Settings, wecom_client: WeComClient | None = None) -> None:
        self.settings = settings
        self.wecom_client = wecom_client or WeComClient(settings)

    def close(self) -> None:
        self.wecom_client.close()

    def create_transaction(
        self, session: Session, device_id: str
    ) -> tuple[WeComAuthTransaction, str, str]:
        poll_secret = new_secret()
        oauth_state_secret = new_secret() if not self.settings.enable_fake_wecom else None
        transaction = WeComAuthTransaction(
            device_id=device_id,
            poll_secret_hash=hash_secret(poll_secret),
            oauth_state_hash=hash_secret(oauth_state_secret) if oauth_state_secret else None,
            expires_at=utc_now()
            + timedelta(seconds=self.settings.auth_transaction_ttl_seconds),
        )
        session.add(transaction)
        session.flush()
        if self.settings.enable_fake_wecom:
            qr_url = f"aiworkbench://fake-wecom/scan?transaction_id={transaction.id}"
        else:
            state = f"{transaction.id}.{oauth_state_secret}"
            try:
                qr_url = self.wecom_client.login_url(state)
            except WeComAPIError as exc:
                session.rollback()
                raise ServiceError(503, "wecom_not_configured", str(exc)) from exc
        add_audit(
            session,
            action="auth.wecom.transaction.created",
            resource_type="auth_transaction",
            resource_id=transaction.id,
            result="success",
            metadata={"device_id_hash": hash_secret(device_id)},
        )
        session.commit()
        return transaction, poll_secret, qr_url

    def complete_wecom_callback(
        self, session: Session, *, code: str, state: str
    ) -> WeComAuthTransaction:
        try:
            transaction_id, oauth_state_secret = state.split(".", maxsplit=1)
        except ValueError as exc:
            raise ServiceError(400, "wecom_state_invalid", "企业微信回调 state 无效") from exc
        transaction = session.get(WeComAuthTransaction, transaction_id)
        if (
            not transaction
            or not transaction.oauth_state_hash
            or not secrets.compare_digest(
                transaction.oauth_state_hash, hash_secret(oauth_state_secret)
            )
        ):
            raise ServiceError(400, "wecom_state_invalid", "企业微信回调 state 无效")
        self._validate_pending_transaction(session, transaction)
        try:
            identity = self.wecom_client.resolve_identity(code)
        except WeComAPIError as exc:
            add_audit(
                session,
                action="auth.wecom.callback.failed",
                resource_type="auth_transaction",
                resource_id=transaction.id,
                result="failure",
                metadata={"error_type": type(exc).__name__},
            )
            session.commit()
            raise ServiceError(502, "wecom_identity_failed", str(exc)) from exc
        return self._approve_transaction(
            session,
            transaction,
            wecom_userid=identity.user_id,
            display_name=identity.display_name,
            department_code=identity.department_code,
            is_admin=False,
        )

    def poll_transaction(
        self, session: Session, transaction_id: str, poll_secret: str
    ) -> tuple[WeComAuthTransaction, str | None]:
        transaction = session.get(WeComAuthTransaction, transaction_id)
        if not transaction or not secrets.compare_digest(
            transaction.poll_secret_hash, hash_secret(poll_secret)
        ):
            raise ServiceError(404, "auth_transaction_not_found", "登录事务不存在")
        if transaction.status == "pending" and transaction.expires_at <= utc_now():
            transaction.status = "expired"
            session.commit()
        exchange_code: str | None = None
        if transaction.status == "approved":
            exchange_code = new_secret()
            transaction.exchange_code_hash = hash_secret(exchange_code)
            session.commit()
        return transaction, exchange_code

    def fake_approve(
        self,
        session: Session,
        transaction_id: str,
        approval: FakeWeComApproval,
    ) -> WeComAuthTransaction:
        if not self.settings.enable_fake_wecom:
            raise ServiceError(404, "fake_wecom_disabled", "开发扫码入口未启用")
        transaction = session.get(WeComAuthTransaction, transaction_id)
        if not transaction:
            raise ServiceError(404, "auth_transaction_not_found", "登录事务不存在")
        self._validate_pending_transaction(session, transaction)
        return self._approve_transaction(
            session,
            transaction,
            wecom_userid=approval.wecom_userid,
            display_name=approval.display_name,
            department_code=approval.department_code,
            is_admin=approval.is_admin,
        )

    def _validate_pending_transaction(
        self, session: Session, transaction: WeComAuthTransaction
    ) -> None:
        if transaction.expires_at <= utc_now():
            transaction.status = "expired"
            session.commit()
            raise ServiceError(410, "auth_transaction_expired", "登录二维码已过期")
        if transaction.status != "pending":
            raise ServiceError(409, "auth_transaction_state", "登录事务状态不可批准")

    def _approve_transaction(
        self,
        session: Session,
        transaction: WeComAuthTransaction,
        *,
        wecom_userid: str,
        display_name: str,
        department_code: str,
        is_admin: bool,
    ) -> WeComAuthTransaction:
        user = session.scalar(select(User).where(User.wecom_userid == wecom_userid))
        if user is None:
            user = User(
                wecom_userid=wecom_userid,
                display_name=display_name,
                department_code=department_code,
                is_admin=is_admin,
            )
            session.add(user)
            session.flush()
        else:
            user.display_name = display_name
            user.department_code = department_code
            user.is_admin = is_admin
            user.status = "active"
        transaction.user_id = user.id
        transaction.status = "approved"
        transaction.approved_at = utc_now()
        add_audit(
            session,
            action="auth.wecom.transaction.approved",
            resource_type="auth_transaction",
            resource_id=transaction.id,
            result="success",
            actor_user_id=user.id,
        )
        session.commit()
        return transaction

    def exchange_token(
        self, session: Session, transaction_id: str, exchange_code: str
    ) -> tuple[str, UserSession]:
        transaction = session.get(WeComAuthTransaction, transaction_id)
        if not transaction or transaction.status != "approved":
            raise ServiceError(409, "auth_transaction_state", "登录事务尚未批准")
        if transaction.expires_at <= utc_now():
            transaction.status = "expired"
            session.commit()
            raise ServiceError(410, "auth_transaction_expired", "登录事务已过期")
        if not transaction.exchange_code_hash or not secrets.compare_digest(
            transaction.exchange_code_hash, hash_secret(exchange_code)
        ):
            raise ServiceError(401, "exchange_code_invalid", "登录交换码无效")
        user = session.get(User, transaction.user_id)
        if not user or user.status != "active":
            raise ServiceError(403, "user_inactive", "用户未激活或已被禁用")
        access_token = new_secret()
        absolute_expires_at = None
        if self.settings.session_absolute_days > 0:
            absolute_expires_at = utc_now() + timedelta(
                days=self.settings.session_absolute_days
            )
        user_session = UserSession(
            user_id=user.id,
            device_id=transaction.device_id,
            token_hash=hash_secret(access_token),
            absolute_expires_at=absolute_expires_at,
        )
        session.add(user_session)
        transaction.status = "exchanged"
        transaction.exchanged_at = utc_now()
        transaction.exchange_code_hash = None
        session.flush()
        add_audit(
            session,
            action="auth.session.created",
            resource_type="session",
            resource_id=user_session.id,
            result="success",
            actor_user_id=user.id,
            session_id=user_session.id,
            metadata={"device_id_hash": hash_secret(transaction.device_id)},
        )
        session.commit()
        return access_token, user_session

    def authenticate(self, session: Session, access_token: str) -> Principal:
        token_hash = hash_secret(access_token)
        user_session = session.scalar(
            select(UserSession).where(UserSession.token_hash == token_hash)
        )
        if not user_session or user_session.status != "active":
            raise ServiceError(401, "session_invalid", "登录会话无效")
        now = utc_now()
        idle_deadline = user_session.last_activity_at + timedelta(
            days=self.settings.session_idle_days
        )
        absolute_expired = (
            user_session.absolute_expires_at is not None
            and user_session.absolute_expires_at <= now
        )
        if idle_deadline <= now or absolute_expired:
            user_session.status = "expired"
            session.commit()
            raise ServiceError(401, "session_expired", "登录会话已过期，需要重新扫码")
        user = session.get(User, user_session.user_id)
        if not user or user.status != "active":
            raise ServiceError(403, "user_inactive", "用户已被禁用")
        user_session.last_activity_at = now
        session.commit()
        return Principal(user=user, user_session=user_session)


class PromptService:
    @staticmethod
    def create_prompt(
        session: Session, principal: Principal, data: PromptCreate
    ) -> PromptPackage:
        if not principal.user.is_admin:
            raise ServiceError(403, "admin_required", "需要管理员权限")
        duplicate = session.scalar(
            select(PromptPackage).where(
                PromptPackage.name == data.name,
                PromptPackage.version == data.version,
            )
        )
        if duplicate:
            raise ServiceError(409, "prompt_version_exists", "Prompt 版本已存在")
        prompt = PromptPackage(
            name=data.name,
            purpose=data.purpose,
            version=data.version,
            system_prompt=data.system_prompt,
            variables_schema=data.variables_schema,
            allowed_tools=data.allowed_tools,
            status=data.status,
            created_by=principal.user.id,
            published_at=utc_now() if data.status == "published" else None,
            expires_at=data.expires_at,
        )
        session.add(prompt)
        session.flush()
        add_audit(
            session,
            action="prompt.created",
            resource_type="prompt_package",
            resource_id=prompt.id,
            result="success",
            actor_user_id=principal.user.id,
            session_id=principal.user_session.id,
            metadata={
                "name": prompt.name,
                "version": prompt.version,
                "status": prompt.status,
                "content_hash": hash_secret(prompt.system_prompt),
            },
        )
        session.commit()
        return prompt

    @staticmethod
    def assign_prompt(
        session: Session,
        principal: Principal,
        prompt_id: str,
        data: PromptAssignmentCreate,
    ) -> PromptAssignment:
        if not principal.user.is_admin:
            raise ServiceError(403, "admin_required", "需要管理员权限")
        prompt = session.get(PromptPackage, prompt_id)
        if not prompt:
            raise ServiceError(404, "prompt_not_found", "Prompt 不存在")
        if data.subject_type != "all" and not data.subject_id:
            raise ServiceError(422, "subject_id_required", "分配目标不能为空")
        assignment = PromptAssignment(
            prompt_id=prompt.id,
            subject_type=data.subject_type,
            subject_id=data.subject_id,
            required=data.required,
        )
        session.add(assignment)
        add_audit(
            session,
            action="prompt.assigned",
            resource_type="prompt_package",
            resource_id=prompt.id,
            result="success",
            actor_user_id=principal.user.id,
            session_id=principal.user_session.id,
            metadata={
                "subject_type": data.subject_type,
                "subject_id_hash": hash_secret(data.subject_id) if data.subject_id else "",
                "required": data.required,
            },
        )
        session.commit()
        return assignment

    @staticmethod
    def effective_prompts(session: Session, user: User) -> list[PromptView]:
        now = utc_now()
        rows = session.execute(
            select(PromptPackage, PromptAssignment.required)
            .join(PromptAssignment, PromptAssignment.prompt_id == PromptPackage.id)
            .where(
                PromptPackage.status == "published",
                or_(PromptPackage.expires_at.is_(None), PromptPackage.expires_at > now),
                or_(
                    PromptAssignment.subject_type == "all",
                    (
                        (PromptAssignment.subject_type == "user")
                        & (PromptAssignment.subject_id == user.id)
                    ),
                    (
                        (PromptAssignment.subject_type == "department")
                        & (PromptAssignment.subject_id == user.department_code)
                    ),
                ),
            )
            .order_by(PromptPackage.name, PromptPackage.version.desc())
        ).all()
        seen: set[str] = set()
        result: list[PromptView] = []
        for prompt, required in rows:
            if prompt.name in seen:
                continue
            seen.add(prompt.name)
            view = PromptView.model_validate(prompt)
            result.append(view.model_copy(update={"required": required}))
        return result


class FakeModelProvider:
    name = "fake-company-model"

    @staticmethod
    def respond(content: str, prompt_names: list[str]) -> str:
        prompt_note = f"，已应用 {len(prompt_names)} 个企业功能 Prompt" if prompt_names else ""
        return (
            f"已收到你的请求{prompt_note}。这是开发环境的 Fake 模型回复："
            f"{content[:160]}"
        )


class ChatService:
    @staticmethod
    def create_conversation(
        session: Session, principal: Principal, title: str
    ) -> Conversation:
        conversation = Conversation(user_id=principal.user.id, title=title)
        session.add(conversation)
        session.flush()
        add_audit(
            session,
            action="conversation.created",
            resource_type="conversation",
            resource_id=conversation.id,
            result="success",
            actor_user_id=principal.user.id,
            session_id=principal.user_session.id,
        )
        session.commit()
        return conversation

    @staticmethod
    def respond(
        session: Session,
        principal: Principal,
        conversation_id: str,
        content: str,
        logical_model: str,
    ) -> ChatResponse:
        conversation = session.get(Conversation, conversation_id)
        if not conversation or conversation.user_id != principal.user.id:
            raise ServiceError(404, "conversation_not_found", "对话不存在")
        prompts = PromptService.effective_prompts(session, principal.user)
        prompt_names = [f"{item.name}@{item.version}" for item in prompts]
        request_id = new_trace_id()
        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=content,
            model_request_id=request_id,
        )
        response_text = FakeModelProvider.respond(content, prompt_names)
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=response_text,
            model_request_id=request_id,
        )
        input_text = "\n".join(item.system_prompt for item in prompts) + content
        input_tokens = max(1, math.ceil(len(input_text) / 4))
        output_tokens = max(1, math.ceil(len(response_text) / 4))
        usage = UsageRecord(
            user_id=principal.user.id,
            conversation_id=conversation.id,
            request_id=request_id,
            logical_model=logical_model,
            actual_model=FakeModelProvider.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            usage_source="estimated",
        )
        conversation.updated_at = utc_now()
        session.add_all((user_message, assistant_message, usage))
        session.flush()
        add_audit(
            session,
            action="ai.response.completed",
            resource_type="conversation",
            resource_id=conversation.id,
            result="success",
            actor_user_id=principal.user.id,
            session_id=principal.user_session.id,
            trace_id=request_id,
            metadata={
                "logical_model": logical_model,
                "actual_model": FakeModelProvider.name,
                "usage_source": "estimated",
                "total_tokens": usage.total_tokens,
                "prompt_versions": prompt_names,
                "input_content_hash": hash_secret(content),
            },
        )
        session.commit()
        return ChatResponse(
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            content=response_text,
            usage=UsageView(
                request_id=request_id,
                logical_model=logical_model,
                actual_model=FakeModelProvider.name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                source="estimated",
            ),
            applied_prompts=prompt_names,
        )

    @staticmethod
    def usage_summary(session: Session, user_id: str) -> UsageSummary:
        row = session.execute(
            select(
                func.coalesce(func.sum(UsageRecord.input_tokens), 0),
                func.coalesce(func.sum(UsageRecord.output_tokens), 0),
                func.coalesce(func.sum(UsageRecord.total_tokens), 0),
                func.count(UsageRecord.id),
            ).where(UsageRecord.user_id == user_id)
        ).one()
        sources = session.execute(
            select(UsageRecord.usage_source, func.count(UsageRecord.id))
            .where(UsageRecord.user_id == user_id)
            .group_by(UsageRecord.usage_source)
        ).all()
        return UsageSummary(
            input_tokens=int(row[0]),
            output_tokens=int(row[1]),
            total_tokens=int(row[2]),
            request_count=int(row[3]),
            source_breakdown={str(name): int(count) for name, count in sources},
        )
