"""屏幕扫描助手 — 程序入口。

运行方式（开发）：
    python main.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

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


def run_selftest(out_path: str) -> int:
    """打包自检：绘制测试图 → 离线 OCR → 结果写入 out_path。

    用于验证 exe 中 OCR 引擎与模型是否完整打包。
    """
    import json

    from PySide6.QtGui import QColor, QFont, QImage, QPainter

    from src.config import tmp_dir
    from src.ocr_engine import OcrEngine

    img = QImage(820, 240, QImage.Format_RGB32)  # noqa: F841
    img.fill(QColor("white"))
    p = QPainter(img)
    p.setPen(QColor("black"))
    p.setFont(QFont("Microsoft YaHei", 22))
    p.drawText(20, 46, "屏幕扫描助手 ScreenScan")
    p.drawText(20, 100, "功能测试 12345 Hello")
    p.drawText(20, 154, "离线识别自检")
    p.end()
    path = str(tmp_dir() / "selftest.png")
    img.save(path, "PNG")

    engine = OcrEngine()
    try:
        items = engine.recognize_sync(path)
    except Exception as e:
        result = {"ok": False, "error": str(e), "count": 0, "text": ""}
    else:
        text = " ".join(it["text"] for it in items)
        result = {
            "ok": ("屏幕扫描助手" in text) and ("12345" in text),
            "count": len(items),
            "text": text,
        }
    try:
        Path(out_path).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def main() -> int:
    QApplication.setApplicationName(APP_NAME)
    QApplication.setApplicationDisplayName(APP_TITLE)
    app = QApplication(sys.argv)

    # 打包自检模式：--selftest <输出json路径>
    if "--selftest" in sys.argv:
        idx = sys.argv.index("--selftest")
        out_path = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else "selftest.json"
        return run_selftest(out_path)

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
