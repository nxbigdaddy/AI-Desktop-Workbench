from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest  # noqa: E402

from ai_desktop.app import create_application  # noqa: E402
from ai_desktop.application import DesktopApplicationService  # noqa: E402
from ai_desktop.local_store import LocalStore  # noqa: E402
from ai_desktop.login_window import LoginWindow  # noqa: E402
from ai_desktop.main_window import MainWindow  # noqa: E402


class _Vault:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def put(self, secret: str, reference: str | None = None) -> str:
        key = reference or "credential:test"
        self.values[key] = secret
        return key

    def get(self, reference: str) -> str:
        return self.values[reference]

    def delete(self, reference: str) -> None:
        self.values.pop(reference, None)


class _LoginPlatform:
    access_token: str | None = None

    def create_wecom_transaction(self, device_id: str) -> dict[str, Any]:
        return {
            "transaction_id": "tx-ui",
            "poll_secret": "poll-secret-long-enough-for-ui",
            "qr_url": f"aiworkbench://login/{device_id}",
            "expires_at": "2026-08-08T12:00:00",
            "mode": "fake",
        }

    def fake_approve_wecom(self, transaction_id: str, **_: Any) -> dict[str, Any]:
        return {"transaction_id": transaction_id, "status": "approved"}

    def poll_wecom_transaction(self, *_: Any) -> dict[str, Any]:
        return {"status": "approved", "exchange_code": "exchange-code-long-enough"}

    def exchange_token(self, *_: Any) -> dict[str, Any]:
        self.access_token = "ui-access-token"
        return {
            "access_token": self.access_token,
            "session_id": "ui-session",
            "idle_timeout_days": 10,
            "user": {
                "id": "ui-user",
                "wecom_userid": "ui-user",
                "display_name": "界面测试用户",
                "department_code": "qa",
                "is_admin": False,
            },
        }

    def client_prompts(self) -> list[dict[str, Any]]:
        return []

    def me(self) -> dict[str, Any]:
        raise RuntimeError("no stored session")


class MainWindowSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = create_application(["ui-smoke-test"])

    def setUp(self) -> None:
        self.window = MainWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_initial_screen_is_chat(self) -> None:
        self.assertEqual(self.window._current_nav, "chat")
        self.assertEqual(self.window.content_stack.currentIndex(), 0)
        self.assertFalse(self.window.context_panel.isHidden())

    def test_navigation_switches_module_surface(self) -> None:
        for key in self.window.PLACEHOLDERS:
            self.window.switch_navigation(key)
            self.assertEqual(self.window._current_nav, key)
            self.assertEqual(
                self.window.content_stack.currentIndex(),
                self.window._placeholder_indexes[key],
            )
        self.window.switch_navigation("chat")
        self.assertFalse(self.window.context_panel.isHidden())

    def test_local_demo_message_can_be_sent(self) -> None:
        before = self.window.messages_layout.count()
        self.window.composer.input.setPlainText("生成一份周报")
        self.window.composer._send()
        self.app.processEvents()
        self.assertEqual(self.window.composer.input.toPlainText(), "")
        self.assertEqual(self.window.messages_layout.count(), before + 1)

    def test_plan_revision_focuses_composer(self) -> None:
        self.window.composer.focus_input("请调整计划：")
        self.assertEqual(self.window.composer.input.toPlainText(), "请调整计划：")
        self.assertTrue(self.window.composer.input.hasFocus())


class LoginWindowSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = create_application(["login-ui-smoke-test"])

    def test_development_login_window_completes_without_qr_scan(self) -> None:
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            store = LocalStore(Path(temporary) / "client.db")
            service = DesktopApplicationService(
                platform=_LoginPlatform(),  # type: ignore[arg-type]
                local_store=store,
                vault=_Vault(),
            )
            window = LoginWindow(service)
            users: list[dict[str, Any]] = []
            window.authenticated.connect(users.append)
            try:
                window.show()
                for _ in range(100):
                    self.app.processEvents()
                    if window.login_button.isVisible():
                        break
                    QTest.qWait(10)
                self.assertTrue(window.login_button.isVisible())
                self.assertEqual(window.login_button.text(), "登录")
                self.assertTrue(window.dev_login_panel.isVisible())
                window.login_button.click()
                for _ in range(300):
                    self.app.processEvents()
                    if users:
                        break
                    QTest.qWait(10)
                self.assertEqual(users[0]["display_name"], "界面测试用户")
            finally:
                window.close()
                self.app.processEvents()
                store.close()


if __name__ == "__main__":
    unittest.main()
