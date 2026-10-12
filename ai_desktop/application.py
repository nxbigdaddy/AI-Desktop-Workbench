from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .local_store import LocalStore
from .platform_client import PlatformClient, PlatformClientError


class Vault(Protocol):
    def put(self, secret: str, reference: str | None = None) -> str: ...

    def get(self, reference: str) -> str: ...

    def delete(self, reference: str) -> None: ...


@dataclass(frozen=True, slots=True)
class LoginTransaction:
    transaction_id: str
    poll_secret: str
    qr_url: str
    expires_at: str
    mode: str


@dataclass(frozen=True, slots=True)
class LoginResult:
    status: str
    user: dict[str, Any] | None = None


class DesktopApplicationService:
    """Coordinate platform calls, OS credentials, and the local SQLite mirror."""

    def __init__(
        self,
        *,
        platform: PlatformClient,
        local_store: LocalStore,
        vault: Vault,
    ) -> None:
        self.platform = platform
        self.local_store = local_store
        self.vault = vault
        self.login_transaction: LoginTransaction | None = None

    def restore_session(self) -> LoginResult:
        login = self.local_store.latest_login()
        if login is None:
            return LoginResult(status="login_required")
        try:
            self.platform.access_token = self.vault.get(str(login["credential_ref"]))
            user = self.platform.me()
            self.local_store.touch_login(str(login["session_id"]))
            self.sync_prompts()
        except (PlatformClientError, RuntimeError):
            self.platform.access_token = None
            return LoginResult(status="login_required")
        return LoginResult(status="authenticated", user=user)

    def begin_wecom_login(self) -> LoginTransaction:
        device_id = self.local_store.get_or_create_device_id()
        result = self.platform.create_wecom_transaction(device_id)
        transaction = LoginTransaction(
            transaction_id=str(result["transaction_id"]),
            poll_secret=str(result["poll_secret"]),
            qr_url=str(result["qr_url"]),
            expires_at=str(result["expires_at"]),
            mode=str(result["mode"]),
        )
        self.login_transaction = transaction
        return transaction

    def simulate_wecom_scan(
        self,
        *,
        wecom_userid: str = "dev-user",
        display_name: str = "开发用户",
        department_code: str = "development",
        is_admin: bool = True,
    ) -> None:
        transaction = self._require_login_transaction()
        if transaction.mode != "fake":
            raise RuntimeError("真实企业微信模式不允许模拟扫码")
        self.platform.fake_approve_wecom(
            transaction.transaction_id,
            wecom_userid=wecom_userid,
            display_name=display_name,
            department_code=department_code,
            is_admin=is_admin,
        )

    def poll_wecom_login(self) -> LoginResult:
        transaction = self._require_login_transaction()
        status = self.platform.poll_wecom_transaction(
            transaction.transaction_id, transaction.poll_secret
        )
        if status["status"] != "approved" or not status.get("exchange_code"):
            return LoginResult(status=str(status["status"]), user=status.get("user"))
        token = self.platform.exchange_token(
            transaction.transaction_id, str(status["exchange_code"])
        )
        credential_ref = self.vault.put(str(token["access_token"]))
        device_id = self.local_store.get_or_create_device_id()
        self.local_store.save_login(
            user=token["user"],
            session_id=str(token["session_id"]),
            device_id=device_id,
            credential_ref=credential_ref,
            idle_timeout_days=int(token["idle_timeout_days"]),
        )
        self.sync_prompts()
        return LoginResult(status="authenticated", user=token["user"])

    def sync_prompts(self) -> list[dict[str, Any]]:
        prompts = self.platform.client_prompts()
        self.local_store.replace_prompts(prompts)
        return prompts

    def create_conversation(self, title: str) -> dict[str, Any]:
        conversation = self.platform.create_conversation(title)
        self.local_store.save_conversation(conversation)
        return conversation

    def send_message(
        self,
        conversation_id: str,
        content: str,
        *,
        logical_model: str = "general-fast",
    ) -> dict[str, Any]:
        response = self.platform.send_message(
            conversation_id, content, logical_model=logical_model
        )
        self.local_store.save_chat_response(user_content=content, response=response)
        return response

    def _require_login_transaction(self) -> LoginTransaction:
        if self.login_transaction is None:
            raise RuntimeError("尚未创建企业微信登录事务")
        return self.login_transaction
