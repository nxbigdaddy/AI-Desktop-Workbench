from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_PATHS = {
    "home": '<path d="M3 10.5 12 3l9 7.5"/><path d="M5.5 9.5V21h13V9.5"/><path d="M9.5 21v-7h5v7"/>',
    "chat": '<path d="M20 15a4 4 0 0 1-4 4H8l-5 3v-7a5 5 0 0 1-1-3V8a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z"/><path d="M7 9h10M7 13h7"/>',
    "tasks": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/><path d="m6.5 8 .7.7 1.3-1.5"/>',
    "file": '<path d="M6 2h8l5 5v15H6z"/><path d="M14 2v6h5M9 13h6M9 17h6"/>',
    "knowledge": '<path d="M4 4.5A3.5 3.5 0 0 1 7.5 1H12v19H7.5A3.5 3.5 0 0 0 4 23z"/><path d="M20 4.5A3.5 3.5 0 0 0 16.5 1H12v19h4.5A3.5 3.5 0 0 1 20 23z"/>',
    "mail": '<rect x="2" y="4" width="20" height="16" rx="3"/><path d="m3 6 9 7 9-7"/>',
    "building": '<path d="M3 22h18M5 22V6l7-4 7 4v16"/><path d="M9 9h1M14 9h1M9 13h1M14 13h1M10 22v-5h4v5"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.8 1.8 0 0 0 .35 2l.1.1-2.8 2.8-.1-.1a1.8 1.8 0 0 0-2-.35 1.8 1.8 0 0 0-1.1 1.65V21H10v-.1a1.8 1.8 0 0 0-1.1-1.65 1.8 1.8 0 0 0-2 .35l-.1.1L4 17l.1-.1a1.8 1.8 0 0 0 .35-2A1.8 1.8 0 0 0 2.8 13H2v-4h.8a1.8 1.8 0 0 0 1.65-1.1 1.8 1.8 0 0 0-.35-2L4 5.8 6.8 3l.1.1a1.8 1.8 0 0 0 2 .35A1.8 1.8 0 0 0 10 1.8V1h4v.8a1.8 1.8 0 0 0 1.1 1.65 1.8 1.8 0 0 0 2-.35l.1-.1L20 5.8l-.1.1a1.8 1.8 0 0 0-.35 2A1.8 1.8 0 0 0 21.2 9h.8v4h-.8A1.8 1.8 0 0 0 19.4 15z"/>',
    "search": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/>',
    "shield": '<path d="M12 2 20 5v6c0 5.5-3.5 9-8 11-4.5-2-8-5.5-8-11V5z"/><path d="m8.5 12 2.2 2.2 4.8-5"/>',
    "paperclip": '<path d="m20 11.5-8.7 8.7a5 5 0 0 1-7.1-7.1l9.4-9.4a3.5 3.5 0 1 1 5 5l-9.4 9.4a2 2 0 0 1-2.8-2.8l8.7-8.7"/>',
    "send": '<path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "spark": '<path d="m12 2 1.3 4.7L18 8l-4.7 1.3L12 14l-1.3-4.7L6 8l4.7-1.3z"/><path d="m19 14 .7 2.3L22 17l-2.3.7L19 20l-.7-2.3L16 17l2.3-.7z"/><path d="m5 15 .6 1.9 1.9.6-1.9.6L5 20l-.6-1.9-1.9-.6 1.9-.6z"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "lock": '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
    "check": '<path d="m5 12 4 4L19 6"/>',
    "chevron": '<path d="m9 18 6-6-6-6"/>',
}


@lru_cache(maxsize=128)
def icon(name: str, color: str = "#667085", size: int = 20) -> QIcon:
    paths = _PATHS.get(name, _PATHS["grid"])
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{paths}</svg>'''
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
