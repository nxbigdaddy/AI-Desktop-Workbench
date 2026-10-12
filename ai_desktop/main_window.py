from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .application import DesktopApplicationService
from .icons import icon
from .widgets import (
    AssistantMessage,
    Composer,
    ContextCard,
    IconButton,
    NavButton,
    PlaceholderPage,
    ToolRow,
    UserMessage,
    label,
)


class MainWindow(QMainWindow):
    """Primary desktop shell for the enterprise AI assistant prototype."""

    NAVIGATION = [
        ("home", "首页", "home", None),
        ("chat", "AI 对话", "chat", None),
        ("tasks", "任务中心", "tasks", "2"),
        ("files", "文件与制品", "file", None),
        ("knowledge", "知识库", "knowledge", None),
        ("mail", "邮件助手", "mail", None),
        ("enterprise", "企业应用", "building", None),
        ("plugins", "应用与插件", "grid", None),
    ]

    PLACEHOLDERS = {
        "home": ("工作台首页", "后续将在这里聚合常用任务、待办事项和团队推荐能力。", "home"),
        "tasks": ("任务中心", "集中查看运行中、等待确认、失败和已完成的 Agent 任务。", "tasks"),
        "files": ("文件与制品", "管理 AI 生成的 Word、Excel、PPT、PDF 及其来源版本。", "file"),
        "knowledge": ("知识库", "浏览个人与团队知识库，并连接公司 MaxKB 专业版。", "knowledge"),
        "mail": ("邮件助手", "在人工确认下完成邮件摘要、起草、回复和附件处理。", "mail"),
        "enterprise": ("企业应用", "通过受控连接器访问公司内部系统和可信数据。", "building"),
        "plugins": ("应用与插件", "查看由管理员授权、签名并统一分发的办公能力。", "grid"),
        "settings": ("设置与帮助", "管理客户端偏好、本地工作区、通知和诊断信息。", "settings"),
    }

    def __init__(self, application_service: DesktopApplicationService | None = None) -> None:
        super().__init__()
        self.application_service = application_service
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chat")
        self._chat_future: Future[dict[str, Any]] | None = None
        self._conversation_id: str | None = None
        self.setWindowTitle("企业 AI 工作台")
        self.setWindowIcon(icon("spark", "#3168E0", 24))
        self.resize(1440, 900)
        self.setMinimumSize(1120, 700)
        self._nav_buttons: dict[str, NavButton] = {}
        self._placeholder_indexes: dict[str, int] = {}
        self._current_nav = "chat"
        self._build_ui()
        self._bind_shortcuts()
        self.switch_navigation("chat")

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())

        workspace = QWidget()
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        workspace_layout.addWidget(self._build_topbar())

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        self.content_stack = QStackedWidget()
        self.chat_page = self._build_chat_page()
        self.content_stack.addWidget(self.chat_page)
        for key, (title, description, icon_name) in self.PLACEHOLDERS.items():
            page = PlaceholderPage(
                title,
                description,
                icon_name,
                action=self._go_to_chat,
            )
            self._placeholder_indexes[key] = self.content_stack.addWidget(page)
        body_layout.addWidget(self.content_stack, 1)
        self.context_panel = self._build_context_panel()
        body_layout.addWidget(self.context_panel)
        workspace_layout.addWidget(body, 1)
        root_layout.addWidget(workspace, 1)
        self.setCentralWidget(root)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(232)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(15, 18, 15, 15)
        layout.setSpacing(5)

        brand = QHBoxLayout()
        brand.setContentsMargins(8, 0, 4, 16)
        brand.setSpacing(10)
        mark = QLabel()
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(36, 36)
        mark.setPixmap(icon("spark", "#FFFFFF", 19).pixmap(19, 19))
        mark.setStyleSheet("background:#3168E0; border-radius:10px;")
        copy = QVBoxLayout()
        copy.setSpacing(1)
        copy.addWidget(label("企业 AI 工作台", "brandName"))
        copy.addWidget(label("AI WORKBENCH", "brandCaption"))
        brand.addWidget(mark)
        brand.addLayout(copy)
        brand.addStretch(1)
        layout.addLayout(brand)

        layout.addWidget(label("工作区", "sectionLabel"))
        for key, text, icon_name, badge in self.NAVIGATION:
            button = NavButton(key, text, icon_name, badge)
            button.activated.connect(self.switch_navigation)
            self._nav_buttons[key] = button
            layout.addWidget(button)

        layout.addStretch(1)
        layout.addWidget(label("系统", "sectionLabel"))
        settings = NavButton("settings", "设置与帮助", "settings")
        settings.activated.connect(self.switch_navigation)
        self._nav_buttons["settings"] = settings
        layout.addWidget(settings)
        layout.addSpacing(8)

        user_card = QFrame()
        user_card.setObjectName("userCard")
        user_layout = QHBoxLayout(user_card)
        user_layout.setContentsMargins(10, 9, 9, 9)
        user_layout.setSpacing(9)
        self.user_avatar = label("AI", "avatar")
        self.user_avatar.setFixedSize(34, 34)
        self.user_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        user_copy = QVBoxLayout()
        user_copy.setSpacing(1)
        self.user_name = label("未登录", "userName")
        self.user_connection = label("●  演示模式 · 未连接", "userStatus")
        user_copy.addWidget(self.user_name)
        user_copy.addWidget(self.user_connection)
        user_layout.addWidget(self.user_avatar)
        user_layout.addLayout(user_copy, 1)
        chevron = QLabel()
        chevron.setPixmap(icon("chevron", "#8A94A6", 14).pixmap(14, 14))
        user_layout.addWidget(chevron)
        layout.addWidget(user_card)
        return sidebar

    def _build_topbar(self) -> QWidget:
        topbar = QFrame()
        topbar.setObjectName("topbar")
        topbar.setFixedHeight(68)
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(25, 0, 22, 0)
        layout.setSpacing(10)

        search_wrap = QWidget()
        search_wrap.setFixedWidth(350)
        search_layout = QHBoxLayout(search_wrap)
        search_layout.setContentsMargins(0, 0, 0, 0)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("globalSearch")
        self.search_input.setFixedHeight(39)
        self.search_input.setPlaceholderText("搜索对话、任务和文件")
        search_icon = QLabel(self.search_input)
        search_icon.setPixmap(icon("search", "#8290A5", 16).pixmap(16, 16))
        search_icon.setFixedSize(18, 18)
        search_icon.move(13, 10)
        search_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        shortcut = label("Ctrl K", "shortcutHint")
        shortcut.setParent(self.search_input)
        shortcut.adjustSize()
        shortcut.move(288, 8)
        shortcut.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        search_layout.addWidget(self.search_input)
        layout.addWidget(search_wrap)
        layout.addStretch(1)

        usage = QFrame()
        usage.setObjectName("usageChip")
        usage.setFixedSize(112, 39)
        usage_layout = QHBoxLayout(usage)
        usage_layout.setContentsMargins(10, 0, 10, 0)
        usage_layout.setSpacing(7)
        usage_icon = QLabel()
        usage_icon.setPixmap(icon("spark", "#3168E0", 15).pixmap(15, 15))
        usage_layout.addWidget(usage_icon)
        usage_layout.addWidget(label("本月用量", "contextLabel"))
        usage_layout.addStretch(1)
        usage_layout.addWidget(label("62%", "usageValue"))
        layout.addWidget(usage)

        notification = IconButton("bell", "通知")
        notification.clicked.connect(lambda: self._show_status("当前没有新的系统通知"))
        layout.addWidget(notification)
        help_button = QPushButton("帮助")
        help_button.setObjectName("ghostButton")
        help_button.setFixedHeight(36)
        help_button.clicked.connect(lambda: self.switch_navigation("settings"))
        layout.addWidget(help_button)
        return topbar

    def _build_chat_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(26, 22, 26, 18)
        layout.setSpacing(0)

        header = QHBoxLayout()
        title_copy = QVBoxLayout()
        title_copy.setSpacing(3)
        title_copy.addWidget(label("AI 对话  /  经营分析", "pageEyebrow"))
        title_copy.addWidget(label("7 月经营分析", "pageTitle"))
        title_copy.addWidget(label("今天 09:42 更新 · 仅你可见", "pageMeta"))
        header.addLayout(title_copy)
        header.addStretch(1)
        share = QPushButton("导出对话")
        share.setObjectName("secondaryButton")
        share.setCursor(Qt.CursorShape.PointingHandCursor)
        share.clicked.connect(lambda: self._show_status("对话导出将在后续接入文档模块"))
        header.addWidget(share)
        more = IconButton("grid", "更多操作", size=36, icon_size=17)
        header.addWidget(more)
        layout.addLayout(header)
        layout.addSpacing(17)

        self.message_scroll = QScrollArea()
        self.message_scroll.setWidgetResizable(True)
        self.message_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        messages = QWidget()
        self.messages_layout = QVBoxLayout(messages)
        self.messages_layout.setContentsMargins(6, 5, 12, 14)
        self.messages_layout.setSpacing(20)
        self.messages_layout.addStretch(1)
        self.message_scroll.setWidget(messages)
        layout.addWidget(self.message_scroll, 1)

        # Create the composer before callbacks capture it from the plan card.
        self.composer = Composer()

        self._add_user_message(
            "读取我刚刚选择的三份 7 月经营报表，统一指标口径，"
            "分析销售和回款变化，并生成一份内部汇报 PPT。"
        )
        assistant = AssistantMessage(
            "我已识别到 3 份 Excel 文件。为了避免覆盖原文件，我会在受控工作区中读取数据，"
            "完成汇总后生成新的 PPTX 草稿。开始前，请确认下面的执行计划。",
            with_plan=True,
        )
        if assistant.plan_card:
            assistant.plan_card.plan_requested.connect(
                lambda: self._show_status("计划已展开：4 个步骤，预计 3–5 分钟")
            )
            assistant.plan_card.start_requested.connect(self._start_demo_task)
            assistant.plan_card.revise_requested.connect(
                lambda: self.composer.focus_input("请调整计划：")
            )
        self._add_message_widget(assistant)

        composer_wrap = QHBoxLayout()
        composer_wrap.addStretch(1)
        self.composer.send_requested.connect(self._send_message)
        self.composer.attach_requested.connect(self._select_attachments)
        self.composer.model_changed.connect(self._model_changed)
        composer_wrap.addWidget(self.composer, 1)
        composer_wrap.addStretch(1)
        layout.addLayout(composer_wrap)
        layout.addSpacing(9)

        status = QFrame()
        status.setObjectName("statusStrip")
        status.setFixedHeight(30)
        status_layout = QHBoxLayout(status)
        status_layout.setContentsMargins(10, 0, 10, 0)
        shield = QLabel()
        shield.setPixmap(icon("shield", "#17845B", 14).pixmap(14, 14))
        self.status_text = label(
            "企业数据受策略保护 · AI 生成内容请核对后使用", "statusText"
        )
        status_layout.addWidget(shield)
        status_layout.addWidget(self.status_text)
        status_layout.addStretch(1)
        status_layout.addWidget(label("连接正常  ●", "userStatus"))
        layout.addWidget(status)
        return page

    def _build_context_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("contextPanel")
        panel.setFixedWidth(292)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(17, 22, 17, 18)
        layout.setSpacing(13)

        header = QHBoxLayout()
        header.addWidget(label("本轮上下文", "contextTitle"))
        header.addStretch(1)
        info = IconButton("shield", "安全与权限说明", size=30, icon_size=15)
        info.clicked.connect(lambda: self._show_status("本轮仅使用已授权的公司内部能力"))
        header.addWidget(info)
        layout.addLayout(header)
        layout.addWidget(ContextCard())

        layout.addSpacing(3)
        layout.addWidget(label("本月用量", "contextSection"))
        usage_row = QHBoxLayout()
        usage_row.addWidget(label("62,140 / 100,000 Token", "contextValue"))
        usage_row.addStretch(1)
        usage_row.addWidget(label("62%", "usageValue"))
        layout.addLayout(usage_row)
        progress = QProgressBar()
        progress.setObjectName("usageBar")
        progress.setRange(0, 100)
        progress.setValue(62)
        progress.setTextVisible(False)
        layout.addWidget(progress)
        layout.addWidget(label("达到 90% 时将提醒你", "cardCaption"))

        layout.addSpacing(5)
        layout.addWidget(label("已授权工具", "contextSection"))
        layout.addWidget(ToolRow("file", "本地文件", "仅限已选择目录 · 只读"))
        layout.addWidget(ToolRow("knowledge", "MaxKB", "个人与共享知识库"))
        layout.addWidget(ToolRow("building", "经营数据", "公司系统 · 只读"))

        layout.addSpacing(5)
        layout.addWidget(label("本轮引用", "contextSection"))
        reference = QFrame()
        reference.setObjectName("contextCard")
        reference_layout = QVBoxLayout(reference)
        reference_layout.setContentsMargins(12, 10, 12, 10)
        reference_layout.setSpacing(4)
        reference_layout.addWidget(label("已选择 3 个文件", "contextValue"))
        reference_layout.addWidget(label("销售报表 · 回款报表 · 目标表", "cardCaption"))
        layout.addWidget(reference)
        layout.addStretch(1)

        clear_context = QPushButton("清除本轮上下文")
        clear_context.setObjectName("secondaryButton")
        clear_context.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_context.clicked.connect(lambda: self._show_status("演示模式：上下文未实际清除"))
        layout.addWidget(clear_context)
        return panel

    def _bind_shortcuts(self) -> None:
        search = QShortcut(QKeySequence("Ctrl+K"), self)
        search.activated.connect(self.search_input.setFocus)
        chat = QShortcut(QKeySequence("Ctrl+N"), self)
        chat.activated.connect(lambda: self.switch_navigation("chat"))

    def _go_to_chat(self) -> None:
        self.switch_navigation("chat")

    def switch_navigation(self, key: str) -> None:
        if key not in self._nav_buttons:
            return
        self._current_nav = key
        for button_key, button in self._nav_buttons.items():
            button.set_active(button_key == key)
        if key == "chat":
            self.content_stack.setCurrentIndex(0)
            self.context_panel.show()
        else:
            self.content_stack.setCurrentIndex(self._placeholder_indexes[key])
            self.context_panel.hide()

    def _add_user_message(self, text: str) -> None:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(70, 0, 0, 0)
        row_layout.addStretch(1)
        row_layout.addWidget(UserMessage(text))
        self._add_message_widget(row)

    def _add_message_widget(self, widget: QWidget) -> None:
        index = max(0, self.messages_layout.count() - 1)
        self.messages_layout.insertWidget(index, widget)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        bar = self.message_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _send_message(self, text: str) -> None:
        if self._chat_future is not None:
            self._show_status("上一条消息仍在处理中，请稍候")
            return
        self._add_user_message(text)
        if self.application_service is None:
            self._send_demo_message()
            return
        self._show_status("正在调用公司统一模型服务…")
        self._chat_future = self._executor.submit(self._send_platform_message, text)
        QTimer.singleShot(50, self._check_chat_future)

    def _send_demo_message(self) -> None:
        self._show_status("已发送到演示会话")
        QTimer.singleShot(
            450,
            lambda: self._add_message_widget(
                AssistantMessage(
                    "这是当前主界面原型的本地演示回复。接入公司 AI 访问服务后，"
                    "这里将显示真实的流式结果、引用和工具调用状态。"
                )
            ),
        )

    def _send_platform_message(self, text: str) -> dict[str, Any]:
        service = self.application_service
        if service is None:
            raise RuntimeError("平台服务未初始化")
        if self._conversation_id is None:
            conversation = service.create_conversation("桌面端新对话")
            self._conversation_id = str(conversation["id"])
        return service.send_message(self._conversation_id, text)

    def _check_chat_future(self) -> None:
        future = self._chat_future
        if future is None:
            return
        if not future.done():
            QTimer.singleShot(50, self._check_chat_future)
            return
        self._chat_future = None
        try:
            response = future.result()
        except RuntimeError as exc:
            self._show_status(f"消息发送失败：{exc}")
            self._add_message_widget(AssistantMessage("暂时无法完成请求，请检查平台连接后重试。"))
            return
        self._add_message_widget(AssistantMessage(str(response["content"])))
        usage = response["usage"]
        self._show_status(f"本次使用 {usage['total_tokens']} Token，记录已同步")

    def set_user_profile(self, user: dict[str, Any]) -> None:
        display_name = str(user.get("display_name") or "企业用户")
        self.user_name.setText(display_name)
        self.user_avatar.setText(display_name[:1])
        self.user_connection.setText("●  企业账号已连接")

    def _start_demo_task(self) -> None:
        self._show_status("任务已加入任务中心：月度经营分析（演示）")

    def _select_attachments(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择用于本轮对话的文件",
            "",
            "办公文件 (*.docx *.xlsx *.pptx *.pdf *.txt);;所有文件 (*.*)",
        )
        if files:
            self._show_status(f"已选择 {len(files)} 个文件（尚未上传）")

    def _model_changed(self, model: str) -> None:
        self._show_status(f"本轮模型已切换为：{model}")

    def _show_status(self, text: str) -> None:
        self.status_text.setText(text)
        QTimer.singleShot(
            3500,
            lambda: self.status_text.setText(
                "企业数据受策略保护 · AI 生成内容请核对后使用"
            ),
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._executor.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)
