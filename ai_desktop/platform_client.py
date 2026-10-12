from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx


class PlatformClientError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class PlatformClient:
    def __init__(
        self,
        base_url: str,
        *,
        access_token: str | None = None,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.access_token = access_token
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
            headers={"User-Agent": "EnterpriseAIWorkbenchDesktop/0.1.0"},
        )

    def close(self) -> None:
        self.client.close()

    def _headers(self) -> dict[str, str]:
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = {**self._headers(), **kwargs.pop("headers", {})}
        try:
            response = self.client.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise PlatformClientError(0, "network_error", str(exc)) from exc
        if response.is_error:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            raise PlatformClientError(
                response.status_code,
                str(payload.get("code") or "platform_error"),
                str(payload.get("message") or payload.get("detail") or "平台请求失败"),
            )
        if response.status_code == 204:
            return None
        return response.json()

    def create_wecom_transaction(self, device_id: str) -> dict[str, Any]:
        return self._request(
            "POST", "/api/v1/auth/wecom/transactions", json={"device_id": device_id}
        )

    def poll_wecom_transaction(
        self, transaction_id: str, poll_secret: str
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/auth/wecom/transactions/poll",
            json={"transaction_id": transaction_id, "poll_secret": poll_secret},
        )

    def fake_approve_wecom(
        self,
        transaction_id: str,
        *,
        wecom_userid: str,
        display_name: str,
        department_code: str = "",
        is_admin: bool = False,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/dev/auth/wecom/transactions/{transaction_id}/approve",
            json={
                "wecom_userid": wecom_userid,
                "display_name": display_name,
                "department_code": department_code,
                "is_admin": is_admin,
            },
        )

    def exchange_token(self, transaction_id: str, exchange_code: str) -> dict[str, Any]:
        result = self._request(
            "POST",
            "/api/v1/auth/token",
            json={"transaction_id": transaction_id, "exchange_code": exchange_code},
        )
        self.access_token = str(result["access_token"])
        return result

    def me(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/me")

    def create_conversation(self, title: str) -> dict[str, Any]:
        return self._request("POST", "/api/v1/conversations", json={"title": title})

    def send_message(
        self,
        conversation_id: str,
        content: str,
        *,
        logical_model: str = "general-fast",
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": content, "logical_model": logical_model},
        )

    def stream_message(
        self,
        conversation_id: str,
        content: str,
        *,
        logical_model: str = "general-fast",
    ) -> Iterator[dict[str, Any]]:
        headers = self._headers()
        try:
            with self.client.stream(
                "POST",
                f"/api/v1/conversations/{conversation_id}/responses",
                headers=headers,
                json={"content": content, "logical_model": logical_model},
            ) as response:
                response.raise_for_status()
                event_name = "message"
                for line in response.iter_lines():
                    if line.startswith("event: "):
                        event_name = line.removeprefix("event: ")
                    elif line.startswith("data: "):
                        import json

                        payload = json.loads(line.removeprefix("data: "))
                        payload.setdefault("event", event_name)
                        yield payload
        except httpx.HTTPError as exc:
            raise PlatformClientError(0, "network_error", str(exc)) from exc

    def usage_summary(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/usage/me/summary")

    def client_prompts(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/client/prompts")
