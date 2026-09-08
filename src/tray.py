"""系统托盘。"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .config import APP_TITLE
from .hotkeys import pretty_hotkey


class Tray(QSystemTrayIcon):
    toggle_requested = Signal()
    fullscreen_requested = Signal()
    quit_requested = Signal()

    def __init__(self, icon: QIcon, hotkey_capture: str = "alt+s", parent: QObject | None = None):
        super().__init__(icon, parent)
        self.setToolTip(f"{APP_TITLE} — {pretty_hotkey(hotkey_capture)} 框选识别")
        menu = QMenu()
        act_show = menu.addAction("显示主窗口")
        act_show.triggered.connect(self.toggle_requested.emit)
        act_full = menu.addAction("全屏扫描")
        act_full.triggered.connect(self.fullscreen_requested.emit)
        menu.addSeparator()
        act_quit = menu.addAction("退出")
        act_quit.triggered.connect(self.quit_requested.emit)
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)
        self.show()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.toggle_requested.emit()

    def update_hint(self, hotkey_capture: str) -> None:
        self.setToolTip(f"{APP_TITLE} — {pretty_hotkey(hotkey_capture)} 框选识别")
