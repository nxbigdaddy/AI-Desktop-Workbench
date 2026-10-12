from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ai_desktop.application import DesktopApplicationService
from ai_desktop.local_store import LocalStore


class MemoryVault:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def put(self, secret: str, reference: str | None = None) -> str:
        key = reference or f"ref-{len(self.values) + 1}"
        self.values[key] = secret
        return key

    def get(self, reference: str) -> str:
        return self.values[reference]

    def delete(self, reference: str) -> None:
        self.values.pop(reference, None)


class StubPlatform:
    access_token: str | None = None

    def create_wecom_transaction(self, device_id: str) -> dict[str, Any]:
        assert device_id
        return {
            "transaction_id": "tx-1",
            "poll_secret": "poll-secret-with-enough-length",
            "qr_url": "aiworkbench://fake-wecom/scan?transaction_id=tx-1",
            "expires_at": "2026-08-08T03:00:00",
            "mode": "fake",
        }

    def fake_approve_wecom(self, transaction_id: str, **_: Any) -> dict[str, Any]:
        assert transaction_id == "tx-1"
        return {"status": "approved"}

    def poll_wecom_transaction(
        self, transaction_id: str, poll_secret: str
    ) -> dict[str, Any]:
        assert transaction_id == "tx-1"
        assert poll_secret == "poll-secret-with-enough-length"
        return {
            "status": "approved",
            "exchange_code": "exchange-code-with-enough-length",
            "user": {"id": "user-1"},
        }

    def exchange_token(self, transaction_id: str, exchange_code: str) -> dict[str, Any]:
        assert transaction_id == "tx-1"
        assert exchange_code == "exchange-code-with-enough-length"
        self.access_token = "secret-access-token"
        return {
            "access_token": self.access_token,
            "session_id": "session-1",
            "idle_timeout_days": 10,
            "user": {
                "id": "user-1",
                "wecom_userid": "dev-user",
                "display_name": "开发用户",
                "department_code": "development",
                "is_admin": True,
            },
        }

    def client_prompts(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "prompt-1",
                "name": "weekly-report",
                "purpose": "周报",
                "version": 1,
                "system_prompt": "生成周报",
                "variables_schema": {},
                "allowed_tools": [],
                "required": True,
                "expires_at": None,
            }
        ]

    def me(self) -> dict[str, Any]:
        assert self.access_token == "secret-access-token"
        return {
            "id": "user-1",
            "wecom_userid": "dev-user",
            "display_name": "开发用户",
            "department_code": "development",
            "is_admin": True,
        }

    def create_conversation(self, title: str) -> dict[str, Any]:
        return {
            "id": "conversation-1",
            "title": title,
            "created_at": "2026-08-08T02:00:00",
            "updated_at": "2026-08-08T02:00:00",
        }

    def send_message(
        self, conversation_id: str, content: str, *, logical_model: str
    ) -> dict[str, Any]:
        assert conversation_id == "conversation-1"
        return {
            "conversation_id": conversation_id,
            "user_message_id": "message-user-1",
            "assistant_message_id": "message-ai-1",
            "content": f"回复：{content}",
            "usage": {
                "request_id": "request-1",
                "logical_model": logical_model,
                "actual_model": "fake-company-model",
                "input_tokens": 4,
                "output_tokens": 6,
                "total_tokens": 10,
                "source": "estimated",
            },
            "applied_prompts": ["weekly-report@1"],
        }


def test_local_store_keeps_secrets_outside_sqlite(tmp_path: Path) -> None:
    store = LocalStore(tmp_path / "client.db")
    try:
        store.save_login(
            user={
                "id": "user-1",
                "wecom_userid": "dev-user",
                "display_name": "开发用户",
                "department_code": "development",
                "is_admin": True,
            },
            session_id="session-1",
            device_id="device-1",
            credential_ref="credential:one",
            idle_timeout_days=10,
        )
        columns = {
            row[1]
            for row in store.connection.execute("PRAGMA table_info(auth_metadata)").fetchall()
        }
        assert "access_token" not in columns
        assert "refresh_token" not in columns
        row = store.connection.execute("SELECT * FROM auth_metadata").fetchone()
        assert row["credential_ref"] == "credential:one"
    finally:
        store.close()


def test_prompt_sync_replaces_revoked_prompts(tmp_path: Path) -> None:
    store = LocalStore(tmp_path / "client.db")
    try:
        store.replace_prompts(
            [
                {
                    "id": "p1",
                    "name": "one",
                    "purpose": "test",
                    "version": 1,
                    "system_prompt": "first",
                    "variables_schema": {},
                    "allowed_tools": [],
                    "required": True,
                    "expires_at": None,
                },
                {
                    "id": "p2",
                    "name": "two",
                    "purpose": "test",
                    "version": 1,
                    "system_prompt": "second",
                    "variables_schema": {},
                    "allowed_tools": [],
                    "required": False,
                    "expires_at": None,
                },
            ]
        )
        assert {item["prompt_id"] for item in store.list_prompts()} == {"p1", "p2"}
        store.replace_prompts(
            [
                {
                    "id": "p2",
                    "name": "two",
                    "purpose": "updated",
                    "version": 1,
                    "system_prompt": "second-updated",
                    "variables_schema": {},
                    "allowed_tools": ["files.read"],
                    "required": True,
                    "expires_at": None,
                }
            ]
        )
        prompts = store.list_prompts()
        assert [item["prompt_id"] for item in prompts] == ["p2"]
        assert prompts[0]["purpose"] == "updated"
    finally:
        store.close()


def test_desktop_service_completes_login_chat_and_local_mirror(tmp_path: Path) -> None:
    store = LocalStore(tmp_path / "client.db")
    vault = MemoryVault()
    platform = StubPlatform()
    service = DesktopApplicationService(
        platform=platform,  # type: ignore[arg-type]
        local_store=store,
        vault=vault,
    )
    try:
        transaction = service.begin_wecom_login()
        assert transaction.mode == "fake"
        service.simulate_wecom_scan()
        result = service.poll_wecom_login()
        assert result.status == "authenticated"
        assert list(vault.values.values()) == ["secret-access-token"]
        assert store.list_prompts()[0]["name"] == "weekly-report"

        restored = service.restore_session()
        assert restored.status == "authenticated"
        assert restored.user and restored.user["display_name"] == "开发用户"

        conversation = service.create_conversation("本地闭环")
        response = service.send_message(conversation["id"], "生成周报")
        assert response["usage"]["total_tokens"] == 10
        messages = store.connection.execute(
            "SELECT role, content FROM messages ORDER BY created_at, role DESC"
        ).fetchall()
        assert {row["role"] for row in messages} == {"user", "assistant"}
        usage = store.connection.execute("SELECT * FROM usage_cache").fetchone()
        assert usage["total_tokens"] == 10
    finally:
        store.close()


def test_local_schema_is_valid_sqlite(tmp_path: Path) -> None:
    store = LocalStore(tmp_path / "client.db")
    store.close()
    connection = sqlite3.connect(tmp_path / "client.db")
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()
