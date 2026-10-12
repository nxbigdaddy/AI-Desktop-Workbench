from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str = "development"
    database_url: str = "sqlite:///runtime-data/platform.db"
    api_base_url: str = "http://127.0.0.1:8765"
    enable_fake_wecom: bool = True
    session_idle_days: int = 10
    session_absolute_days: int = 0
    auth_transaction_ttl_seconds: int = 300
    prompt_retention_days: int = 180
    wecom_corp_id: str = ""
    wecom_agent_id: str = ""
    wecom_secret: str = ""
    wecom_secret_ref: str = ""
    wecom_callback_url: str = ""
    model_proxy_base_url: str = ""
    model_proxy_credential_ref: str = ""

    @classmethod
    def from_environment(cls) -> Settings:
        return cls(
            environment=os.getenv("AIW_ENVIRONMENT", "development"),
            database_url=os.getenv(
                "AIW_DATABASE_URL", "sqlite:///runtime-data/platform.db"
            ),
            api_base_url=os.getenv("AIW_API_BASE_URL", "http://127.0.0.1:8765"),
            enable_fake_wecom=_as_bool(
                os.getenv("AIW_ENABLE_FAKE_WECOM"), default=True
            ),
            session_idle_days=int(os.getenv("AIW_SESSION_IDLE_DAYS", "10")),
            session_absolute_days=int(os.getenv("AIW_SESSION_ABSOLUTE_DAYS", "0")),
            auth_transaction_ttl_seconds=int(
                os.getenv("AIW_AUTH_TRANSACTION_TTL_SECONDS", "300")
            ),
            prompt_retention_days=int(
                os.getenv("AIW_PROMPT_RETENTION_DAYS", "180")
            ),
            wecom_corp_id=os.getenv("AIW_WECOM_CORP_ID", ""),
            wecom_agent_id=os.getenv("AIW_WECOM_AGENT_ID", ""),
            wecom_secret=os.getenv("AIW_WECOM_SECRET", ""),
            wecom_secret_ref=os.getenv("AIW_WECOM_SECRET_REF", ""),
            wecom_callback_url=os.getenv("AIW_WECOM_CALLBACK_URL", ""),
            model_proxy_base_url=os.getenv("AIW_MODEL_PROXY_BASE_URL", ""),
            model_proxy_credential_ref=os.getenv(
                "AIW_MODEL_PROXY_CREDENTIAL_REF", ""
            ),
        )

    def ensure_local_directories(self) -> None:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            return
        raw_path = self.database_url.removeprefix(prefix)
        if raw_path == ":memory:":
            return
        Path(raw_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_environment()
