import json
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import Database
from .models import AuditEvent, PromptAssignment
from .schemas import (
    AuditEventView,
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationView,
    FakeWeComApproval,
    PromptAssignmentCreate,
    PromptCreate,
    PromptView,
    TokenExchangeRequest,
    TokenResponse,
    UsageSummary,
    UserProfile,
    WeComTransactionCreate,
    WeComTransactionCreated,
    WeComTransactionPoll,
    WeComTransactionStatus,
)
from .services import (
    AuthService,
    ChatService,
    Principal,
    PromptService,
    ServiceError,
)
from .wecom import WeComClient

bearer = HTTPBearer(auto_error=False)


def create_app(
    settings: Settings | None = None,
    *,
    wecom_client: WeComClient | None = None,
) -> FastAPI:
    active_settings = settings or get_settings()
    database = Database(active_settings)
    auth_service = AuthService(active_settings, wecom_client=wecom_client)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        database.create_schema()
        try:
            yield
        finally:
            auth_service.close()
            database.dispose()

    app = FastAPI(
        title="Enterprise AI Workbench Platform API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = active_settings
    app.state.database = database
    app.state.auth_service = auth_service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )

    @app.exception_handler(ServiceError)
    async def handle_service_error(_: Request, exc: ServiceError):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )

    def get_db(request: Request) -> Iterator[Session]:
        yield from request.app.state.database.sessions()

    def get_auth_service(request: Request) -> AuthService:
        return request.app.state.auth_service

    def current_principal(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None, Depends(bearer)
        ],
        auth: Annotated[AuthService, Depends(get_auth_service)],
        session: Annotated[Session, Depends(get_db)],
    ) -> Principal:
        if credentials is None or credentials.scheme.casefold() != "bearer":
            raise HTTPException(status_code=401, detail="缺少 Bearer Token")
        return auth.authenticate(session, credentials.credentials)

    def admin_principal(
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> Principal:
        if not principal.user.is_admin:
            raise HTTPException(status_code=403, detail="需要管理员权限")
        return principal

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def health_ready(session: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
        session.execute(select(1)).scalar_one()
        return {"status": "ready"}

    @app.post(
        "/api/v1/auth/wecom/transactions",
        response_model=WeComTransactionCreated,
        status_code=201,
    )
    def create_wecom_transaction(
        data: WeComTransactionCreate,
        auth: Annotated[AuthService, Depends(get_auth_service)],
        session: Annotated[Session, Depends(get_db)],
    ) -> WeComTransactionCreated:
        transaction, poll_secret, qr_url = auth.create_transaction(session, data.device_id)
        return WeComTransactionCreated(
            transaction_id=transaction.id,
            poll_secret=poll_secret,
            qr_url=qr_url,
            expires_at=transaction.expires_at,
            mode="fake" if auth.settings.enable_fake_wecom else "wecom",
        )

    @app.post(
        "/api/v1/auth/wecom/transactions/poll",
        response_model=WeComTransactionStatus,
    )
    def poll_wecom_transaction(
        data: WeComTransactionPoll,
        auth: Annotated[AuthService, Depends(get_auth_service)],
        session: Annotated[Session, Depends(get_db)],
    ) -> WeComTransactionStatus:
        transaction, exchange_code = auth.poll_transaction(
            session, data.transaction_id, data.poll_secret
        )
        return WeComTransactionStatus(
            transaction_id=transaction.id,
            status=transaction.status,
            expires_at=transaction.expires_at,
            exchange_code=exchange_code,
            user=UserProfile.model_validate(transaction.user)
            if transaction.user
            else None,
        )

    @app.post(
        "/api/v1/dev/auth/wecom/transactions/{transaction_id}/approve",
        response_model=WeComTransactionStatus,
    )
    def fake_approve_wecom_transaction(
        transaction_id: str,
        data: FakeWeComApproval,
        auth: Annotated[AuthService, Depends(get_auth_service)],
        session: Annotated[Session, Depends(get_db)],
    ) -> WeComTransactionStatus:
        transaction = auth.fake_approve(session, transaction_id, data)
        return WeComTransactionStatus(
            transaction_id=transaction.id,
            status=transaction.status,
            expires_at=transaction.expires_at,
            user=UserProfile.model_validate(transaction.user),
        )

    @app.get("/api/v1/auth/wecom/callback", response_class=HTMLResponse)
    def wecom_callback(
        code: str,
        state: str,
        auth: Annotated[AuthService, Depends(get_auth_service)],
        session: Annotated[Session, Depends(get_db)],
    ) -> HTMLResponse:
        auth.complete_wecom_callback(session, code=code, state=state)
        return HTMLResponse(
            """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
            <meta name="viewport" content="width=device-width,initial-scale=1">
            <title>登录成功</title></head><body style="font-family:sans-serif;text-align:center;
            padding:48px;color:#172033"><h2>企业微信登录成功</h2>
            <p>请返回企业 AI 工作台，窗口将自动进入。</p></body></html>""",
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
            },
        )

    @app.post("/api/v1/auth/token", response_model=TokenResponse)
    def exchange_token(
        data: TokenExchangeRequest,
        auth: Annotated[AuthService, Depends(get_auth_service)],
        session: Annotated[Session, Depends(get_db)],
    ) -> TokenResponse:
        access_token, user_session = auth.exchange_token(
            session, data.transaction_id, data.exchange_code
        )
        return TokenResponse(
            access_token=access_token,
            session_id=user_session.id,
            idle_timeout_days=auth.settings.session_idle_days,
            user=UserProfile.model_validate(user_session.user),
        )

    @app.get("/api/v1/me", response_model=UserProfile)
    def get_me(
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> UserProfile:
        return UserProfile.model_validate(principal.user)

    @app.post(
        "/api/v1/conversations", response_model=ConversationView, status_code=201
    )
    def create_conversation(
        data: ConversationCreate,
        principal: Annotated[Principal, Depends(current_principal)],
        session: Annotated[Session, Depends(get_db)],
    ) -> ConversationView:
        return ConversationView.model_validate(
            ChatService.create_conversation(session, principal, data.title)
        )

    @app.post(
        "/api/v1/conversations/{conversation_id}/messages",
        response_model=ChatResponse,
    )
    def create_message(
        conversation_id: str,
        data: ChatRequest,
        principal: Annotated[Principal, Depends(current_principal)],
        session: Annotated[Session, Depends(get_db)],
    ) -> ChatResponse:
        return ChatService.respond(
            session,
            principal,
            conversation_id,
            data.content,
            data.logical_model,
        )

    @app.post("/api/v1/conversations/{conversation_id}/responses")
    def stream_response(
        conversation_id: str,
        data: ChatRequest,
        principal: Annotated[Principal, Depends(current_principal)],
        session: Annotated[Session, Depends(get_db)],
    ) -> StreamingResponse:
        result = ChatService.respond(
            session,
            principal,
            conversation_id,
            data.content,
            data.logical_model,
        )

        def events() -> Iterator[str]:
            created = {"type": "response.created", "request_id": result.usage.request_id}
            yield f"event: response.created\ndata: {json.dumps(created, ensure_ascii=False)}\n\n"
            for offset in range(0, len(result.content), 24):
                payload = {
                    "type": "response.output_text.delta",
                    "delta": result.content[offset : offset + 24],
                }
                yield "event: response.output_text.delta\ndata: " + json.dumps(
                    payload, ensure_ascii=False
                ) + "\n\n"
            completed = {
                "type": "response.completed",
                "response": result.model_dump(mode="json"),
            }
            yield "event: response.completed\ndata: " + json.dumps(
                completed, ensure_ascii=False
            ) + "\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.get("/api/v1/usage/me/summary", response_model=UsageSummary)
    def get_usage_summary(
        principal: Annotated[Principal, Depends(current_principal)],
        session: Annotated[Session, Depends(get_db)],
    ) -> UsageSummary:
        return ChatService.usage_summary(session, principal.user.id)

    @app.post("/api/v1/admin/prompts", response_model=PromptView, status_code=201)
    def create_prompt(
        data: PromptCreate,
        principal: Annotated[Principal, Depends(admin_principal)],
        session: Annotated[Session, Depends(get_db)],
    ) -> PromptView:
        return PromptView.model_validate(
            PromptService.create_prompt(session, principal, data)
        )

    @app.post(
        "/api/v1/admin/prompts/{prompt_id}/assignments", status_code=201
    )
    def assign_prompt(
        prompt_id: str,
        data: PromptAssignmentCreate,
        principal: Annotated[Principal, Depends(admin_principal)],
        session: Annotated[Session, Depends(get_db)],
    ) -> dict[str, str | bool]:
        assignment: PromptAssignment = PromptService.assign_prompt(
            session, principal, prompt_id, data
        )
        return {
            "id": assignment.id,
            "prompt_id": assignment.prompt_id,
            "subject_type": assignment.subject_type,
            "subject_id": assignment.subject_id,
            "required": assignment.required,
        }

    @app.get("/api/v1/client/prompts", response_model=list[PromptView])
    def get_client_prompts(
        principal: Annotated[Principal, Depends(current_principal)],
        session: Annotated[Session, Depends(get_db)],
    ) -> list[PromptView]:
        return PromptService.effective_prompts(session, principal.user)

    @app.get("/api/v1/audit/me", response_model=list[AuditEventView])
    def get_my_audit(
        principal: Annotated[Principal, Depends(current_principal)],
        session: Annotated[Session, Depends(get_db)],
        limit: int = 100,
    ) -> list[AuditEventView]:
        rows = session.scalars(
            select(AuditEvent)
            .where(AuditEvent.actor_user_id == principal.user.id)
            .order_by(AuditEvent.occurred_at.desc())
            .limit(min(max(limit, 1), 500))
        ).all()
        return [AuditEventView.model_validate(item) for item in rows]

    @app.get("/api/v1/admin/audit/events", response_model=list[AuditEventView])
    def get_audit_events(
        _: Annotated[Principal, Depends(admin_principal)],
        session: Annotated[Session, Depends(get_db)],
        limit: int = 100,
    ) -> list[AuditEventView]:
        rows = session.scalars(
            select(AuditEvent)
            .order_by(AuditEvent.occurred_at.desc())
            .limit(min(max(limit, 1), 500))
        ).all()
        return [AuditEventView.model_validate(item) for item in rows]

    return app


app = create_app()


def run() -> None:
    uvicorn.run(
        "platform_api.main:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
    )


if __name__ == "__main__":
    run()
