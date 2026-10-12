from __future__ import annotations

import sys

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .application import DesktopApplicationService
from .credentials import CredentialVault
from .local_store import LocalStore
from .login_window import LoginWindow
from .main_window import MainWindow
from .platform_client import PlatformClient
from .settings import DesktopSettings
from .theme import APP_STYLESHEET


def create_application(argv: list[str] | None = None) -> QApplication:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    instance = QApplication.instance()
    app = instance if isinstance(instance, QApplication) else QApplication(argv or sys.argv)
    app.setApplicationName("企业 AI 工作台")
    app.setOrganizationName("Company")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(APP_STYLESHEET)
    return app


class ApplicationController(QObject):
    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self._closed = False
        settings = DesktopSettings.from_environment()
        settings.ensure_directories()
        self.local_store = LocalStore(settings.database_path)
        self.platform_client = PlatformClient(
            settings.api_base_url,
            timeout_seconds=settings.request_timeout_seconds,
        )
        self.service = DesktopApplicationService(
            platform=self.platform_client,
            local_store=self.local_store,
            vault=CredentialVault(),
        )
        self.login_window = LoginWindow(self.service)
        self.main_window: MainWindow | None = None
        self.login_window.authenticated.connect(self._show_workspace)
        app.aboutToQuit.connect(self.close)

    def start(self) -> None:
        self.login_window.show()

    def _show_workspace(self, user: dict[str, object]) -> None:
        if self.main_window is None:
            self.main_window = MainWindow(self.service)
        self.main_window.set_user_profile(user)
        self.login_window.hide()
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.platform_client.close()
        self.local_store.close()


def run() -> int:
    app = create_application()
    controller = ApplicationController(app)
    controller.start()
    exit_code = app.exec()
    controller.close()
    return exit_code
