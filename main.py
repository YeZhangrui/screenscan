"""屏幕扫描助手 — 程序入口。

运行方式（开发）：
    python main.py
"""
from __future__ import annotations

import os
import sys

# 保证在 PyInstaller 打包环境与开发环境都能 import src
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication, QMessageBox

from src.app_controller import AppController
from src.config import APP_NAME, APP_TITLE, Config, data_dir
from src.history import HistoryStore
from src.hotkeys import HotkeyManager, HotkeySignals
from src.main_window import MainWindow
from src.ocr_engine import OcrEngine
from src.result_window import ResultWindow
from src.theme import apply_theme
from src.tray import Tray
from src.widgets import make_app_icon


def main() -> int:
    QApplication.setApplicationName(APP_NAME)
    QApplication.setApplicationDisplayName(APP_TITLE)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    icon = make_app_icon()
    app.setWindowIcon(icon)

    # 单实例保护：避免重复启动导致热键/托盘冲突
    lock = QLockFile(str(data_dir() / "app.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, APP_TITLE, "屏幕扫描助手已经在运行，请勿重复打开。")
        return 0

    config = Config()
    history = HistoryStore(limit=int(config.get("history_limit", 50)))
    ocr = OcrEngine()
    hotkey_signals = HotkeySignals()
    hotkey_manager = HotkeyManager(hotkey_signals)

    main_win = MainWindow(config, history)
    result_win = ResultWindow(config)
    tray = Tray(icon, str(config.get("hotkey_capture", "alt+s")))
    controller = AppController(config, ocr, main_win, result_win, tray, history)
    controller.set_hotkey_manager(hotkey_manager)

    # —— 事件接线 ——
    def toggle_main() -> None:
        if main_win.isVisible():
            main_win.hide()
        else:
            main_win.show_events()

    hotkey_signals.capture_triggered.connect(controller.start_capture)
    hotkey_signals.fullscreen_triggered.connect(controller.start_fullscreen)
    main_win.capture_clicked.connect(controller.start_capture)
    main_win.fullscreen_clicked.connect(controller.start_fullscreen)
    main_win.upload_clicked.connect(controller.upload_image)
    main_win.settings_clicked.connect(controller.open_settings)
    main_win.open_history.connect(controller.open_history_record)
    tray.toggle_requested.connect(toggle_main)
    tray.fullscreen_requested.connect(controller.start_fullscreen)
    tray.quit_requested.connect(app.quit)
    ocr.signals.finished.connect(controller.on_ocr_done)
    ocr.signals.failed.connect(controller.on_ocr_failed)
    ocr.signals.state_changed.connect(main_win.set_engine_state)
    app.aboutToQuit.connect(hotkey_manager.stop)

    # 启用水久热键
    err = hotkey_manager.apply(
        str(config.get("hotkey_capture", "alt+s")),
        str(config.get("hotkey_fullscreen", "alt+shift+s")),
    )
    if err:
        QMessageBox.warning(main_win, APP_TITLE, err + "\n\n可在「设置」中更换快捷键。")

    # 后台预加载 OCR 模型
    ocr.preload_async()

    tray.show()
    main_win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
