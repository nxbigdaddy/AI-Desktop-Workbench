from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from .config import Settings


class WeComAPIError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class WeComIdentity:
    user_id: str
    display_name: str
    department_code: str


class WeComClient:
    """Server-side adapter for a company's self-built WeCom application."""

    LOGIN_URL = "https://open.work.weixin.qq.com/wwopen/sso/qrConnect"
    API_BASE_URL = "https://qyapi.weixin.qq.com"

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.client = httpx.Client(
            base_url=self.API_BASE_URL,
            timeout=15.0,
            transport=transport,
            headers={"User-Agent": "EnterpriseAIWorkbenchPlatform/0.1.0"},
        )
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0

    def close(self) -> None:
        self.client.close()

    def validate_configuration(self) -> None:
        missing = [
            name
            for name, value in (
                ("AIW_WECOM_CORP_ID", self.settings.wecom_corp_id),
                ("AIW_WECOM_AGENT_ID", self.settings.wecom_agent_id),
                ("AIW_WECOM_CALLBACK_URL", self.settings.wecom_callback_url),
                ("AIW_WECOM_SECRET", self.settings.wecom_secret),
            )
            if not value
        ]
        if missing:
            raise WeComAPIError(f"企业微信配置不完整：{', '.join(missing)}")

    def login_url(self, state: str) -> str:
        self.validate_configuration()
        query = urlencode(
            {
                "appid": self.settings.wecom_corp_id,
                "agentid": self.settings.wecom_agent_id,
                "redirect_uri": self.settings.wecom_callback_url,
                "state": state,
                "lang": "zh",
            }
        )
        return f"{self.LOGIN_URL}?{query}"

    def resolve_identity(self, code: str) -> WeComIdentity:
        access_token = self._application_access_token()
        identity = self._get_json(
            "/cgi-bin/user/getuserinfo",
            params={"access_token": access_token, "code": code},
        )
        user_id = str(identity.get("UserId") or identity.get("userid") or "")
        if not user_id:
            raise WeComAPIError("企业微信未返回企业成员 UserId，请检查应用可见范围")

        display_name = user_id
        department_code = ""
        try:
            profile = self._get_json(
                "/cgi-bin/user/get",
                params={"access_token": access_token, "userid": user_id},
            )
            display_name = str(profile.get("name") or user_id)
            departments = profile.get("department") or []
            if departments:
                department_code = str(departments[0])
        except WeComAPIError:
            # Login remains usable when the app can identify a member but lacks
            # permission to read the detailed address-book profile.
            pass
        return WeComIdentity(user_id, display_name, department_code)

    def _application_access_token(self) -> str:
        self.validate_configuration()
        now = time.monotonic()
        if self._access_token and now < self._access_token_expires_at:
            return self._access_token
        payload = self._get_json(
            "/cgi-bin/gettoken",
            params={
                "corpid": self.settings.wecom_corp_id,
                "corpsecret": self.settings.wecom_secret,
            },
        )
        token = str(payload.get("access_token") or "")
        if not token:
            raise WeComAPIError("企业微信未返回 access_token")
        expires_in = max(120, int(payload.get("expires_in") or 7200))
        self._access_token = token
        self._access_token_expires_at = now + expires_in - 60
        return token

    def _get_json(self, path: str, *, params: dict[str, str]) -> dict[str, Any]:
        try:
            response = self.client.get(path, params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WeComAPIError(f"企业微信接口请求失败：{exc}") from exc
        if int(payload.get("errcode") or 0) != 0:
            code = payload.get("errcode")
            message = payload.get("errmsg") or "unknown error"
            raise WeComAPIError(f"企业微信接口错误 {code}: {message}")
        return dict(payload)
