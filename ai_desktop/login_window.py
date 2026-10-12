from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .application import DesktopApplicationService, LoginResult, LoginTransaction
from .platform_client import PlatformClientError


class LoginWindow(QMainWindow):
    authenticated = Signal(dict)

    def __init__(self, service: DesktopApplicationService) -> None:
        super().__init__()
        self.service = service
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="login")
        self._future: Future[Any] | None = None
        self._future_callback: Callable[[Any], None] | None = None
        self._started = False
        self._login_mode = "fake"
        self._wecom_web_view: QWebEngineView | None = None

        self.setWindowTitle("企业微信登录 · 企业 AI 工作台")
        self.setFixedSize(540, 700)
        self._build_ui()

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(1500)
        self.poll_timer.timeout.connect(self._poll_login)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("loginRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(54, 42, 54, 34)
        layout.setSpacing(14)

        title = QLabel("企业 AI 工作台")
        title.setObjectName("loginTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle = QLabel("登录企业账号")
        self.subtitle.setObjectName("loginSubtitle")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(self.subtitle)
        layout.addSpacing(8)

        qr_card = QFrame()
        qr_card.setObjectName("loginQrCard")
        qr_layout = QVBoxLayout(qr_card)
        qr_layout.setContentsMargins(24, 24, 24, 20)
        qr_layout.setSpacing(12)
        self.qr_stack = QStackedWidget()
        self.qr_stack.setFixedSize(300, 300)
        self.qr_label = QLabel("正在连接统一管理平台…")
        self.qr_label.setObjectName("loginQr")
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setWordWrap(True)
        self.qr_stack.addWidget(self.qr_label)

        self.dev_login_panel = QFrame()
        self.dev_login_panel.setObjectName("loginDevPanel")
        dev_layout = QVBoxLayout(self.dev_login_panel)
        dev_layout.setContentsMargins(30, 42, 30, 42)
        dev_layout.setSpacing(13)
        dev_layout.addStretch(1)
        dev_mark = QLabel("AI")
        dev_mark.setObjectName("loginDevMark")
        dev_mark.setFixedSize(68, 68)
        dev_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dev_layout.addWidget(dev_mark, 0, Qt.AlignmentFlag.AlignHCenter)
        dev_title = QLabel("开发环境登录")
        dev_title.setObjectName("loginDevTitle")
        dev_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dev_layout.addWidget(dev_title)
        dev_description = QLabel("当前阶段暂不启用企业微信扫码\n点击下方按钮即可进入工作台")
        dev_description.setObjectName("loginDevDescription")
        dev_description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dev_layout.addWidget(dev_description)
        dev_layout.addStretch(1)
        self.qr_stack.addWidget(self.dev_login_panel)

        qr_layout.addWidget(self.qr_stack, 0, Qt.AlignmentFlag.AlignHCenter)
        self.status_label = QLabel("正在检查登录状态")
        self.status_label.setObjectName("loginStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        qr_layout.addWidget(self.status_label)
        layout.addWidget(qr_card)

        self.login_button = QPushButton("登录")
        self.login_button.setObjectName("primaryButton")
        self.login_button.setFixedHeight(42)
        self.login_button.hide()
        self.login_button.clicked.connect(self._direct_login)
        layout.addWidget(self.login_button)

        self.retry_button = QPushButton("重试")
        self.retry_button.setObjectName("secondaryButton")
        self.retry_button.setFixedHeight(40)
        self.retry_button.hide()
        self.retry_button.clicked.connect(self._begin_login)
        layout.addWidget(self.retry_button)

        hint_row = QHBoxLayout()
        self.hint = QLabel("登录凭据保存在 Windows 凭据管理器；10 天未使用需重新登录")
        self.hint.setObjectName("loginHint")
        self.hint.setWordWrap(True)
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_row.addWidget(self.hint)
        layout.addLayout(hint_row)
        self.setCentralWidget(root)

    def showEvent(self, event: Any) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._started:
            self._started = True
            QTimer.singleShot(0, self._restore_session)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.poll_timer.stop()
        self._executor.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)

    def _restore_session(self) -> None:
        self._set_busy("正在验证本地登录状态…")
        self._submit(self.service.restore_session, self._on_session_restored)

    def _on_session_restored(self, result: LoginResult) -> None:
        if result.status == "authenticated" and result.user:
            self._complete_login(result.user)
            return
        self._begin_login()

    def _begin_login(self) -> None:
        self.poll_timer.stop()
        self.login_button.hide()
        self.retry_button.hide()
        self.qr_label.clear()
        self._set_busy("正在准备登录…")
        self._submit(self.service.begin_wecom_login, self._on_transaction)

    def _on_transaction(self, transaction: LoginTransaction) -> None:
        self._login_mode = transaction.mode
        if transaction.mode == "fake":
            self.subtitle.setText("开发阶段直接登录")
            self.qr_stack.setCurrentWidget(self.dev_login_panel)
            self.status_label.setText("开发服务已连接，可以直接登录")
            self.login_button.setEnabled(True)
            self.login_button.show()
        else:
            self.subtitle.setText("使用企业微信扫码登录")
            if self._wecom_web_view is not None:
                self.qr_stack.removeWidget(self._wecom_web_view)
                self._wecom_web_view.deleteLater()
            self._wecom_web_view = QWebEngineView()
            self._wecom_web_view.setObjectName("wecomLoginWebView")
            self.qr_stack.addWidget(self._wecom_web_view)
            self.qr_stack.setCurrentWidget(self._wecom_web_view)
            self._wecom_web_view.setUrl(QUrl(transaction.qr_url))
            self.status_label.setText("请使用企业微信扫描二维码并在手机上确认")
            self.hint.setText("登录凭据保存在 Windows 凭据管理器；10 天未使用需重新扫码")
            self.poll_timer.start()

    def _direct_login(self) -> None:
        self.login_button.setEnabled(False)
        self._set_busy("正在登录…")
        self._submit(self.service.simulate_wecom_scan, self._on_scan_simulated)

    def _on_scan_simulated(self, _result: Any) -> None:
        self.status_label.setText("已确认，正在完成登录…")
        self._poll_login()

    def _poll_login(self) -> None:
        if self._future is not None:
            return
        self._submit(self.service.poll_wecom_login, self._on_poll_result)

    def _on_poll_result(self, result: LoginResult) -> None:
        if result.status == "authenticated" and result.user:
            self._complete_login(result.user)
        elif result.status == "pending":
            if self._login_mode == "fake":
                self.status_label.setText("正在完成登录…")
            else:
                self.status_label.setText("等待扫码确认…")
            self.poll_timer.start()
        elif result.status in {"expired", "rejected"}:
            self.poll_timer.stop()
            if self._login_mode == "fake":
                self.status_label.setText("登录请求已失效，请重试")
                self.retry_button.setText("重试")
            else:
                self.status_label.setText("二维码已失效，请重新获取")
                self.retry_button.setText("重新获取二维码")
            self.retry_button.show()

    def _complete_login(self, user: dict[str, Any]) -> None:
        self.poll_timer.stop()
        self.login_button.hide()
        self.retry_button.hide()
        self.status_label.setText(f"登录成功，欢迎 {user['display_name']}")
        QTimer.singleShot(250, lambda: self.authenticated.emit(user))

    def _set_busy(self, message: str) -> None:
        self.status_label.setText(message)
        self.retry_button.hide()

    def _submit(self, task: Callable[[], Any], callback: Callable[[Any], None]) -> None:
        if self._future is not None:
            return
        self._future_callback = callback
        self._future = self._executor.submit(task)
        QTimer.singleShot(40, self._check_future)

    def _check_future(self) -> None:
        future = self._future
        if future is None:
            return
        if not future.done():
            QTimer.singleShot(40, self._check_future)
            return
        callback = self._future_callback
        self._future = None
        self._future_callback = None
        try:
            result = future.result()
        except (PlatformClientError, RuntimeError) as exc:
            self._show_error(exc)
            return
        if callback:
            callback(result)

    def _show_error(self, error: Exception) -> None:
        self.poll_timer.stop()
        self.login_button.setEnabled(True)
        if isinstance(error, PlatformClientError) and error.code == "network_error":
            message = "无法连接统一管理平台，请先启动开发服务后重试"
        else:
            message = str(error) or "登录失败"
        self.status_label.setText(message)
        self.retry_button.show()
