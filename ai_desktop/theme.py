from __future__ import annotations

COLORS = {
    "canvas": "#F4F6FA",
    "surface": "#FFFFFF",
    "surface_alt": "#F8FAFC",
    "surface_blue": "#F2F6FF",
    "primary": "#3168E0",
    "primary_hover": "#2859C2",
    "primary_soft": "#EAF0FF",
    "text": "#172033",
    "text_secondary": "#5F6B7C",
    "text_muted": "#8A94A6",
    "border": "#E5E9F0",
    "border_strong": "#D7DDE7",
    "success": "#17845B",
    "success_soft": "#E8F7F1",
    "warning": "#A86612",
    "warning_soft": "#FFF5E4",
    "danger": "#C64545",
}


APP_STYLESHEET = """
* {
    color: #172033;
    font-family: "Segoe UI", "Microsoft YaHei UI";
    font-size: 13px;
}

QMainWindow, QWidget#appRoot {
    background: #F4F6FA;
}

QWidget#loginRoot {
    background: #F4F7FB;
}

QLabel#loginTitle {
    color: #172033;
    font-size: 25px;
    font-weight: 700;
}

QLabel#loginSubtitle {
    color: #657186;
    font-size: 14px;
}

QFrame#loginQrCard {
    background: #FFFFFF;
    border: 1px solid #E1E7F0;
    border-radius: 16px;
}

QLabel#loginQr {
    background: #FFFFFF;
    border: 1px solid #EEF1F5;
    border-radius: 10px;
    color: #7C8798;
    padding: 8px;
}

QFrame#loginDevPanel {
    background: #F7F9FD;
    border: 1px solid #E3E9F3;
    border-radius: 14px;
}

QLabel#loginDevMark {
    background: #3168E0;
    border-radius: 20px;
    color: #FFFFFF;
    font-size: 22px;
    font-weight: 700;
}

QLabel#loginDevTitle {
    color: #172033;
    font-size: 18px;
    font-weight: 700;
}

QLabel#loginDevDescription {
    color: #6C788D;
    font-size: 12px;
    line-height: 1.5;
}

QLabel#loginStatus {
    color: #46536A;
    font-size: 13px;
    min-height: 34px;
}

QLabel#loginHint {
    color: #8A94A6;
    font-size: 11px;
}

QFrame#sidebar, QFrame#topbar, QFrame#contextPanel {
    background: #FFFFFF;
}

QFrame#sidebar {
    border-right: 1px solid #E5E9F0;
}

QFrame#topbar {
    border-bottom: 1px solid #E5E9F0;
}

QFrame#contextPanel {
    border-left: 1px solid #E5E9F0;
}

QLabel#brandName {
    color: #172033;
    font-size: 15px;
    font-weight: 700;
}

QLabel#brandCaption {
    color: #8A94A6;
    font-size: 10px;
    letter-spacing: 1px;
}

QLabel#sectionLabel {
    color: #98A1B2;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}

QPushButton#navButton {
    background: transparent;
    border: none;
    border-radius: 9px;
    color: #5F6B7C;
    font-size: 13px;
    font-weight: 500;
    padding: 0 12px;
    text-align: left;
}

QPushButton#navButton:hover {
    background: #F4F6FA;
    color: #172033;
}

QPushButton#navButton[active="true"] {
    background: #EAF0FF;
    color: #2859C2;
    font-weight: 700;
}

QLabel#navBadge {
    background: #3168E0;
    border-radius: 8px;
    color: #FFFFFF;
    font-size: 10px;
    font-weight: 700;
    padding: 1px 5px;
}

QFrame#userCard {
    background: #F8FAFC;
    border: 1px solid #E5E9F0;
    border-radius: 12px;
}

QLabel#avatar {
    background: #DCE7FF;
    border-radius: 17px;
    color: #2859C2;
    font-size: 12px;
    font-weight: 700;
}

QLabel#userName {
    font-size: 12px;
    font-weight: 700;
}

QLabel#userStatus {
    color: #17845B;
    font-size: 10px;
}

QLineEdit#globalSearch {
    background: #F7F9FC;
    border: 1px solid #E5E9F0;
    border-radius: 10px;
    color: #172033;
    padding: 0 38px;
    selection-background-color: #DCE7FF;
}

QLineEdit#globalSearch:focus {
    background: #FFFFFF;
    border: 1px solid #9AB5F2;
}

QLabel#shortcutHint {
    background: #FFFFFF;
    border: 1px solid #DDE2EA;
    border-radius: 5px;
    color: #8A94A6;
    font-size: 10px;
    padding: 2px 6px;
}

QPushButton#iconButton {
    background: transparent;
    border: none;
    border-radius: 9px;
}

QPushButton#iconButton:hover {
    background: #F1F4F8;
}

QFrame#usageChip {
    background: #F8FAFC;
    border: 1px solid #E5E9F0;
    border-radius: 10px;
}

QLabel#usageValue {
    color: #3168E0;
    font-size: 12px;
    font-weight: 700;
}

QLabel#pageEyebrow {
    color: #8A94A6;
    font-size: 11px;
}

QLabel#pageTitle {
    color: #172033;
    font-size: 20px;
    font-weight: 700;
}

QLabel#pageMeta {
    color: #7C8798;
    font-size: 11px;
}

QScrollArea, QScrollArea > QWidget > QWidget {
    background: transparent;
    border: none;
}

QScrollBar:vertical {
    background: transparent;
    width: 7px;
    margin: 4px 0;
}

QScrollBar::handle:vertical {
    background: #CFD6E1;
    border-radius: 3px;
    min-height: 36px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QFrame#userBubble {
    background: #EAF0FF;
    border: 1px solid #DCE6FB;
    border-radius: 14px;
}

QLabel#messageRole {
    color: #7C8798;
    font-size: 11px;
    font-weight: 600;
}

QLabel#messageText {
    color: #253147;
    font-size: 13px;
    line-height: 1.5;
}

QLabel#aiMark {
    background: #3168E0;
    border-radius: 16px;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: 800;
}

QFrame#planCard, QFrame#contextCard {
    background: #FFFFFF;
    border: 1px solid #E3E8F0;
    border-radius: 13px;
}

QLabel#cardTitle {
    color: #263249;
    font-size: 13px;
    font-weight: 700;
}

QLabel#cardCaption {
    color: #7C8798;
    font-size: 11px;
}

QLabel#stepNumber {
    background: #EFF3F8;
    border-radius: 10px;
    color: #657186;
    font-size: 10px;
    font-weight: 700;
}

QLabel#stepText {
    color: #4F5B6F;
    font-size: 12px;
}

QPushButton#secondaryButton, QPushButton#ghostButton, QPushButton#primaryButton {
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    min-height: 34px;
    padding: 0 14px;
}

QPushButton#primaryButton {
    background: #3168E0;
    border: 1px solid #3168E0;
    color: #FFFFFF;
}

QPushButton#primaryButton:hover {
    background: #2859C2;
    border-color: #2859C2;
}

QPushButton#secondaryButton {
    background: #FFFFFF;
    border: 1px solid #D9E0EA;
    color: #3B485E;
}

QPushButton#secondaryButton:hover {
    background: #F7F9FC;
    border-color: #BFC9D8;
}

QPushButton#ghostButton {
    background: transparent;
    border: none;
    color: #69758A;
}

QPushButton#ghostButton:hover {
    background: #F3F5F8;
    color: #354158;
}

QFrame#composer {
    background: #FFFFFF;
    border: 1px solid #DCE2EB;
    border-radius: 16px;
}

QFrame#composer[focused="true"] {
    border: 1px solid #9AB5F2;
}

QPlainTextEdit#messageInput {
    background: transparent;
    border: none;
    color: #253147;
    font-size: 13px;
    padding: 0;
}

QComboBox#modelSelect {
    background: #F4F6FA;
    border: none;
    border-radius: 8px;
    color: #40506A;
    font-size: 11px;
    font-weight: 600;
    min-height: 32px;
    padding: 0 10px;
}

QComboBox#modelSelect::drop-down {
    border: none;
    width: 20px;
}

QComboBox#modelSelect QAbstractItemView {
    background: #FFFFFF;
    border: 1px solid #DCE2EB;
    border-radius: 8px;
    selection-background-color: #EAF0FF;
    selection-color: #2859C2;
    padding: 6px;
}

QPushButton#sendButton {
    background: #3168E0;
    border: none;
    border-radius: 17px;
}

QPushButton#sendButton:hover {
    background: #2859C2;
}

QPushButton#sendButton:disabled {
    background: #CAD4E7;
}

QLabel#composerHint {
    color: #9AA3B2;
    font-size: 10px;
}

QLabel#contextTitle {
    color: #263249;
    font-size: 13px;
    font-weight: 700;
}

QLabel#contextSection {
    color: #8A94A6;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}

QLabel#contextLabel {
    color: #7C8798;
    font-size: 11px;
}

QLabel#contextValue {
    color: #263249;
    font-size: 12px;
    font-weight: 650;
}

QLabel#safeTag {
    background: #E8F7F1;
    border-radius: 7px;
    color: #17845B;
    font-size: 10px;
    font-weight: 700;
    padding: 4px 7px;
}

QProgressBar#usageBar {
    background: #E8ECF2;
    border: none;
    border-radius: 3px;
    max-height: 6px;
    min-height: 6px;
}

QProgressBar#usageBar::chunk {
    background: #3168E0;
    border-radius: 3px;
}

QFrame#toolRow {
    background: transparent;
    border: none;
}

QLabel#toolIcon {
    background: #EEF3FB;
    border-radius: 8px;
}

QLabel#toolName {
    color: #354158;
    font-size: 11px;
    font-weight: 600;
}

QLabel#toolScope {
    color: #8A94A6;
    font-size: 9px;
}

QLabel#connectedDot {
    color: #17845B;
    font-size: 13px;
}

QFrame#statusStrip {
    background: #F8FAFC;
    border: 1px solid #E5E9F0;
    border-radius: 9px;
}

QLabel#statusText {
    color: #69758A;
    font-size: 10px;
}

QLabel#placeholderTitle {
    color: #263249;
    font-size: 20px;
    font-weight: 700;
}

QLabel#placeholderBody {
    color: #7C8798;
    font-size: 13px;
}

QToolTip {
    background: #253147;
    border: none;
    color: #FFFFFF;
    padding: 6px 8px;
}
"""
