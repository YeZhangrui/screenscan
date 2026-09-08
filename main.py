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


def run_flowtest(out_path: str, input_image: str | None = None) -> int:
    """端到端链路诊断：截图区域（或指定图片）→ 保存 → 异步识别 → 结果窗口。

    用于复现「识别卡住」类问题，输出各阶段耗时与错误。
    """
    import json as _json
    import logging as _logging
    import time as _time

    from PySide6.QtCore import QEventLoop, QRect, QTimer
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QMessageBox

    from src.capture import grab_region
    from src.config import tmp_dir
    from src.logging_setup import setup_logging

    setup_logging()
    log = _logging.getLogger("flowtest")
    rep: dict = {"stage": "start"}
    try:
        # 复现真实启动路径：先后台预加载，紧接着发起识别（并发场景）
        ocr = OcrEngine()
        ocr.preload_async()
        if input_image:
            from PySide6.QtGui import QPixmap

            pm = QPixmap(input_image)
            rep["input_image"] = input_image
        else:
            screen = QGuiApplication.primaryScreen()
            pm = grab_region(screen, QRect(0, 0, 520, 160))
        rep["stage"] = "grabbed"
        if pm is None or pm.isNull():
            rep["stage"] = "grab_failed"
            Path(out_path).write_text(_json.dumps(rep, ensure_ascii=False), encoding="utf-8")
            return 1
        out = tmp_dir() / "flowtest.png"
        plain = pm.copy()
        plain.setDevicePixelRatio(1.0)
        plain.save(str(out), "PNG")
        rep["stage"] = "saved"

        loop = QEventLoop()
        rep_result = {}

        def on_fin(job, items):
            rep_result["stage"] = "ocr_done"
            rep_result["items"] = len(items)
            rep_result["items_list"] = items
            rep_result["texts"] = [it["text"] for it in items[:6]]
            loop.quit()

        def on_fail(job, msg):
            rep_result["stage"] = "ocr_failed"
            rep_result["error"] = msg
            loop.quit()

        ocr.signals.finished.connect(on_fin)
        ocr.signals.failed.connect(on_fail)
        t0 = _time.perf_counter()
        ocr.recognize_async("flowtest", str(out))
        QTimer.singleShot(90000, loop.quit)
        loop.exec()
        rep["elapsed_s"] = round(_time.perf_counter() - t0, 2)
        rep.update(rep_result)
        rep.setdefault("stage", "ocr_timeout")
        rep["api"] = ocr._api
        if rep_result.get("stage") == "ocr_done":
            # 继续走结果展示与历史链路（用临时目录，不污染真实数据）
            import tempfile as _tempfile

            from src.config import Config as Cfg
            from src.history import HistoryStore
            from src.result_window import ResultWindow
            from src.theme import apply_theme

            apply_theme(QApplication.instance())
            cfg = Cfg()
            his = HistoryStore(root=Path(_tempfile.mkdtemp(prefix="flowtest_")), limit=5)
            rw = ResultWindow(cfg)
            t1 = _time.perf_counter()
            items_list = rep_result.get("items_list") or []
            rw.show_result(pm, items_list, "flowtest")
            his.add("flowtest", " ".join(it["text"] for it in items_list), pm)
            rep["show_result_s"] = round(_time.perf_counter() - t1, 2)
            rep["stage"] = "all_ok"
    except Exception as e:
        import traceback

        rep["stage"] = "exception"
        rep["error"] = str(e)
        rep["trace"] = traceback.format_exc()[-2000:]
    finally:
        try:
            Path(out_path).write_text(_json.dumps(rep, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    print(_json.dumps(rep, ensure_ascii=False))
    return 0 if rep.get("stage") == "all_ok" else 1


def run_autocap(out_path: str) -> int:
    """忠实复现真实应用启动路径（引擎预加载、托盘、主窗、控制器），

    4 秒后自动执行一次真实截图识别链路，观测是否复现卡死。
    """
    import json as _json
    import logging as _logging

    from PySide6.QtCore import QRect, QTimer
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication as _QA

    from src.app_controller import AppController
    from src.config import Config as Cfg
    from src.history import HistoryStore
    from src.hotkeys import HotkeyManager, HotkeySignals
    from src.logging_setup import setup_logging
    from src.main_window import MainWindow
    from src.result_window import ResultWindow
    from src.theme import apply_theme
    from src.tray import Tray
    from src.widgets import make_app_icon

    log_file = setup_logging()
    log = _logging.getLogger("autocap")
    apply_theme(_QA.instance())

    config = Cfg()
    history = HistoryStore(limit=int(config.get("history_limit", 50)))
    ocr = OcrEngine()
    hotkey_manager = HotkeyManager(HotkeySignals())
    main_win = MainWindow(config, history)
    result_win = ResultWindow(config)
    tray = Tray(make_app_icon(), str(config.get("hotkey_capture", "alt+s")))
    controller = AppController(config, ocr, main_win, result_win, tray, history)
    controller.set_hotkey_manager(hotkey_manager)
    ocr.signals.state_changed.connect(main_win.set_engine_state)

    rep: dict = {"stage": "start", "log_file": str(log_file)}

    def on_done(job, items):
        controller.on_ocr_done(job, items)
        rep["stage"] = "done"
        rep["items"] = len(items)
        QTimer.singleShot(2500, _QA.instance().quit)

    def on_fail(job, msg):
        controller.on_ocr_failed(job, msg)
        rep["stage"] = "failed"
        rep["error"] = msg
        QTimer.singleShot(2000, _QA.instance().quit)

    ocr.signals.finished.connect(on_done)
    ocr.signals.failed.connect(on_fail)

    err = hotkey_manager.apply(
        str(config.get("hotkey_capture", "alt+s")),
        str(config.get("hotkey_fullscreen", "alt+shift+s")),
    )
    if err:
        log.warning("热键启用失败：%s", err)

    ocr.preload_async()
    tray.show()
    main_win.show()

    def trigger():
        log.info("== autocap：模拟一次框选识别链路 ==")
        screen = QGuiApplication.primaryScreen()
        controller._grab_region_and_ocr(screen, QRect(0, 0, 760, 260))

    QTimer.singleShot(4000, trigger)
    QTimer.singleShot(90000, _QA.instance().quit)

    _QA.instance().exec()
    rep.setdefault("stage", "timeout")
    try:
        Path(out_path).write_text(_json.dumps(rep, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    log.info("autocap 结束 stage=%s", rep.get("stage"))
    return 0 if rep.get("stage") == "done" else 1


def main() -> int:
    import logging

    from src.logging_setup import setup_logging

    setup_logging()
    log = logging.getLogger("app")
    log.info("== 屏幕扫描助手 启动 ==")

    QApplication.setApplicationName(APP_NAME)
    QApplication.setApplicationDisplayName(APP_TITLE)
    app = QApplication(sys.argv)

    # 打包自检模式：--selftest <输出json路径>
    if "--selftest" in sys.argv:
        idx = sys.argv.index("--selftest")
        out_path = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else "selftest.json"
        return run_selftest(out_path)

    # 端到端链路诊断：--flowtest <输出json路径> [可选输入图片]
    if "--flowtest" in sys.argv:
        idx = sys.argv.index("--flowtest")
        out_path = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else "flowtest.json"
        img = sys.argv[idx + 2] if len(sys.argv) > idx + 2 else None
        return run_flowtest(out_path, img)

    # 真实启动路径复现：--autocap <输出json路径>
    if "--autocap" in sys.argv:
        idx = sys.argv.index("--autocap")
        out_path = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else "autocap.json"
        return run_autocap(out_path)

    app.setQuitOnLastWindowClosed(False)
    icon = make_app_icon()
    app.setWindowIcon(icon)

    # 单实例保护：避免重复启动导致热键/托盘冲突
    lock = QLockFile(str(data_dir() / "app.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, APP_TITLE, "屏幕扫描助手已经在运行，请勿重复打开。")
        return 0

    config = Config()
    apply_theme(app, str(config.get("theme", "system")))

    # 跟随系统：系统深浅色变化时自动切换
    def _on_color_scheme_changed(*_args) -> None:
        apply_theme(app, str(config.get("theme", "system")))

    try:
        app.styleHints().colorSchemeChanged.connect(_on_color_scheme_changed)
    except Exception:  # noqa: BLE001
        pass

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
    tray.capture_requested.connect(controller.start_capture)
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
    log.info("启动完成：热键=%s/%s", config.get("hotkey_capture"), config.get("hotkey_fullscreen"))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
