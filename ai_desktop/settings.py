from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def default_data_root() -> Path:
    configured = os.getenv("AIW_LOCAL_DATA_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return (Path(local_app_data) / "CompanyAIWorkbench").resolve()
    return (Path.home() / ".company-ai-workbench").resolve()


@dataclass(frozen=True, slots=True)
class DesktopSettings:
    api_base_url: str
    data_root: Path
    request_timeout_seconds: float = 30.0

    @classmethod
    def from_environment(cls) -> DesktopSettings:
        return cls(
            api_base_url=os.getenv("AIW_API_BASE_URL", "http://127.0.0.1:8765"),
            data_root=default_data_root(),
            request_timeout_seconds=float(
                os.getenv("AIW_REQUEST_TIMEOUT_SECONDS", "30")
            ),
        )

    @property
    def database_path(self) -> Path:
        return self.data_root / "client.db"

    @property
    def mail_root(self) -> Path:
        return self.data_root / "mail"

    @property
    def artifact_root(self) -> Path:
        return self.data_root / "artifacts"

    def ensure_directories(self) -> None:
        for path in (self.data_root, self.mail_root, self.artifact_root):
            path.mkdir(parents=True, exist_ok=True)

