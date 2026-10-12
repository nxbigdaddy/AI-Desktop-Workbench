from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "windows" if os.name == "nt" else "offscreen")

from PySide6.QtTest import QTest  # noqa: E402

from ai_desktop.app import create_application  # noqa: E402
from ai_desktop.application import LoginResult, LoginTransaction  # noqa: E402
from ai_desktop.login_window import LoginWindow  # noqa: E402


class PreviewLoginService:
    def restore_session(self) -> LoginResult:
        return LoginResult(status="login_required")

    def begin_wecom_login(self) -> LoginTransaction:
        return LoginTransaction(
            transaction_id="preview-transaction",
            poll_secret="preview-poll-secret",
            qr_url="aiworkbench://fake-wecom/scan?transaction_id=preview-transaction",
            expires_at="2026-08-08T12:00:00",
            mode="fake",
        )

    def simulate_wecom_scan(self) -> None:
        return None

    def poll_wecom_login(self) -> LoginResult:
        return LoginResult(status="pending")


def main() -> int:
    output = PROJECT_ROOT / "artifacts" / "login-window.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    app = create_application(["render_login_window"])
    window = LoginWindow(PreviewLoginService())  # type: ignore[arg-type]
    window.show()
    for _ in range(200):
        app.processEvents()
        if window.login_button.isVisible():
            break
        QTest.qWait(10)
    if not window.login_button.isVisible():
        raise RuntimeError("Login preview did not finish loading")
    image = window.grab()
    if not image.save(str(output), "PNG"):
        raise RuntimeError(f"Unable to save screenshot: {output}")
    print(output)
    print(f"{image.width()}x{image.height()}")
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
