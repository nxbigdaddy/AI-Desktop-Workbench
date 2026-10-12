from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QSize, Qt, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .icons import icon


def label(text: str, object_name: str = "") -> QLabel:
    widget = QLabel(text)
    if object_name:
        widget.setObjectName(object_name)
    return widget


def refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class NavButton(QPushButton):
    activated = Signal(str)

    def __init__(
        self,
        key: str,
        text: str,
        icon_name: str,
        badge: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.key = key
        self.icon_name = icon_name
        self.badge_text = badge
        self.setObjectName("navButton")
        self.setProperty("active", False)
        self.setFixedHeight(42)
        self.setIconSize(QSize(18, 18))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(lambda: self.activated.emit(self.key))
        self._badge = QLabel(badge, self) if badge else None
        if self._badge:
            self._badge.setObjectName("navBadge")
            self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.set_active(False)

    def set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        color = "#2859C2" if active else "#68758A"
        self.setIcon(icon(self.icon_name, color, 18))
        refresh_style(self)

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        if self._badge:
            self._badge.adjustSize()
            self._badge.move(
                self.width() - self._badge.width() - 12,
                (self.height() - self._badge.height()) // 2,
            )


class IconButton(QPushButton):
    def __init__(
        self,
        icon_name: str,
        tooltip: str,
        size: int = 38,
        icon_size: int = 19,
        color: str = "#657186",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("iconButton")
        self.setFixedSize(size, size)
        self.setIcon(icon(icon_name, color, icon_size))
        self.setIconSize(QSize(icon_size, icon_size))
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class UserMessage(QFrame):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("userBubble")
        self.setMaximumWidth(600)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(7)
        role = label("你", "messageRole")
        body = label(text, "messageText")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(role)
        layout.addWidget(body)


class StepRow(QWidget):
    def __init__(self, number: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        number_label = label(number, "stepNumber")
        number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        number_label.setFixedSize(21, 21)
        text_label = label(text, "stepText")
        layout.addWidget(number_label)
        layout.addWidget(text_label, 1)


class PlanCard(QFrame):
    plan_requested = Signal()
    start_requested = Signal()
    revise_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("planCard")
        self.setMaximumWidth(680)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(17, 16, 17, 15)
        layout.setSpacing(12)

        heading_row = QHBoxLayout()
        heading_row.setSpacing(10)
        heading_icon = QLabel()
        heading_icon.setPixmap(icon("tasks", "#3168E0", 18).pixmap(18, 18))
        heading_icon.setFixedSize(20, 20)
        heading_copy = QVBoxLayout()
        heading_copy.setSpacing(2)
        heading_copy.addWidget(label("已生成可执行计划", "cardTitle"))
        heading_copy.addWidget(label("预计 3–5 分钟 · 所有写入操作均需确认", "cardCaption"))
        safe = label("受控执行", "safeTag")
        safe.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading_row.addWidget(heading_icon)
        heading_row.addLayout(heading_copy, 1)
        heading_row.addWidget(safe)
        layout.addLayout(heading_row)

        steps = [
            "读取并检查 3 份经营报表",
            "统一字段口径并汇总关键指标",
            "生成趋势图与异常说明",
            "套用公司模板，输出 PPTX 草稿",
        ]
        for index, step in enumerate(steps, start=1):
            layout.addWidget(StepRow(str(index), step))

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 3, 0, 0)
        action_row.setSpacing(8)
        view_button = QPushButton("查看计划")
        view_button.setObjectName("secondaryButton")
        view_button.setCursor(Qt.CursorShape.PointingHandCursor)
        view_button.clicked.connect(self.plan_requested)
        start_button = QPushButton("开始执行")
        start_button.setObjectName("primaryButton")
        start_button.setIcon(icon("check", "#FFFFFF", 15))
        start_button.setIconSize(QSize(15, 15))
        start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        start_button.clicked.connect(self.start_requested)
        revise_button = QPushButton("修改要求")
        revise_button.setObjectName("ghostButton")
        revise_button.setCursor(Qt.CursorShape.PointingHandCursor)
        revise_button.clicked.connect(self.revise_requested)
        action_row.addWidget(view_button)
        action_row.addWidget(start_button)
        action_row.addWidget(revise_button)
        action_row.addStretch(1)
        layout.addLayout(action_row)


class AssistantMessage(QWidget):
    def __init__(
        self,
        text: str,
        with_plan: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)
        mark = label("AI", "aiMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(32, 32)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(mark, 0, Qt.AlignmentFlag.AlignTop)

        body = QVBoxLayout()
        body.setSpacing(11)
        body.addWidget(label("企业 AI 助手", "messageRole"))
        message = label(text, "messageText")
        message.setWordWrap(True)
        message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        message.setMaximumWidth(680)
        body.addWidget(message)
        self.plan_card: PlanCard | None = None
        if with_plan:
            self.plan_card = PlanCard()
            body.addWidget(self.plan_card)
        outer.addLayout(body, 1)


class Composer(QFrame):
    send_requested = Signal(str)
    attach_requested = Signal()
    model_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("composer")
        self.setProperty("focused", False)
        self.setMaximumWidth(840)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 12, 10)
        layout.setSpacing(8)

        self.input = QPlainTextEdit()
        self.input.setObjectName("messageInput")
        self.input.setPlaceholderText("输入问题，或描述一项需要完成的工作…")
        self.input.setFixedHeight(52)
        self.input.setTabChangesFocus(True)
        self.input.installEventFilter(self)
        self.input.textChanged.connect(self._update_send_state)
        layout.addWidget(self.input)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(7)
        attach = IconButton("paperclip", "添加附件", size=32, icon_size=17)
        attach.clicked.connect(self.attach_requested)
        plus = IconButton("plus", "更多能力", size=32, icon_size=17)
        toolbar.addWidget(attach)
        toolbar.addWidget(plus)
        toolbar.addSpacing(2)
        toolbar.addWidget(label("Ctrl + Enter 发送", "composerHint"))
        toolbar.addStretch(1)

        self.model_select = QComboBox()
        self.model_select.setObjectName("modelSelect")
        self.model_select.addItems(["深度推理", "通用快速", "多模态理解"])
        self.model_select.currentTextChanged.connect(self.model_changed)
        toolbar.addWidget(self.model_select)

        self.send_button = QPushButton()
        self.send_button.setObjectName("sendButton")
        self.send_button.setFixedSize(34, 34)
        self.send_button.setIcon(icon("send", "#FFFFFF", 16))
        self.send_button.setIconSize(QSize(16, 16))
        self.send_button.setToolTip("发送")
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.clicked.connect(self._send)
        toolbar.addWidget(self.send_button)
        layout.addLayout(toolbar)
        self._update_send_state()

    def focus_input(self, prefix: str = "") -> None:
        if prefix:
            self.input.setPlainText(prefix)
            self.input.moveCursor(QTextCursor.MoveOperation.End)
        self.input.setFocus()

    def _update_send_state(self) -> None:
        self.send_button.setEnabled(bool(self.input.toPlainText().strip()))

    def _send(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self.send_requested.emit(text)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.input:
            if event.type() == QEvent.Type.FocusIn:
                self.setProperty("focused", True)
                refresh_style(self)
            elif event.type() == QEvent.Type.FocusOut:
                self.setProperty("focused", False)
                refresh_style(self)
            elif event.type() == QEvent.Type.KeyPress:
                key_event = event
                assert isinstance(key_event, QKeyEvent)
                if (
                    key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                    and key_event.modifiers() & Qt.KeyboardModifier.ControlModifier
                ):
                    self._send()
                    return True
        return super().eventFilter(watched, event)


class ContextCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("contextCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 13, 14, 13)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(label("数据安全", "cardTitle"))
        top.addStretch(1)
        top.addWidget(label("公司内部", "safeTag"))
        layout.addLayout(top)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #E8ECF2;")
        layout.addWidget(line)

        self._add_value(layout, "当前模型", "深度推理")
        self._add_value(layout, "处理位置", "公司 AI 代理平台")
        self._add_value(layout, "会话权限", "仅本次会话")

    @staticmethod
    def _add_value(layout: QVBoxLayout, name: str, value: str) -> None:
        row = QHBoxLayout()
        row.addWidget(label(name, "contextLabel"))
        row.addStretch(1)
        row.addWidget(label(value, "contextValue"))
        layout.addLayout(row)


class ToolRow(QFrame):
    def __init__(
        self,
        icon_name: str,
        name: str,
        scope: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("toolRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(9)
        icon_label = QLabel()
        icon_label.setObjectName("toolIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(30, 30)
        icon_label.setPixmap(icon(icon_name, "#496893", 15).pixmap(15, 15))
        copy = QVBoxLayout()
        copy.setSpacing(1)
        copy.addWidget(label(name, "toolName"))
        copy.addWidget(label(scope, "toolScope"))
        layout.addWidget(icon_label)
        layout.addLayout(copy, 1)
        layout.addWidget(label("●", "connectedDot"))


class PlaceholderPage(QWidget):
    def __init__(
        self,
        title: str,
        description: str,
        icon_name: str,
        action: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)
        mark = QLabel()
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setPixmap(icon(icon_name, "#3168E0", 38).pixmap(38, 38))
        mark.setFixedSize(72, 72)
        mark.setStyleSheet("background:#EAF0FF; border-radius:18px;")
        title_label = label(title, "placeholderTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body = label(description, "placeholderBody")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)
        body.setMaximumWidth(420)
        layout.addWidget(mark, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title_label)
        layout.addWidget(body)
        if action:
            button = QPushButton("返回 AI 对话")
            button.setObjectName("primaryButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(action)
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)
