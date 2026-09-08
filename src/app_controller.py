"""应用主控制：串联热键、截图、OCR、结果窗、历史、设置。"""
from __future__ import annotations

import uuid

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import QFileDialog, QMessageBox

from . import autostart
from .capture import grab_fullscreen, grab_region
from .config import APP_TITLE, Config, tmp_dir
from .history import HistoryStore
from .main_window import MainWindow
from .ocr_engine import OcrEngine
from .overlay import ScreenSelector
from .result_window import ResultWindow
from .settings_window import SettingsDialog
from .tray import Tray


class AppController(QObject):
    def __init__(
        self,
        config: Config,
        ocr: OcrEngine,
        main_win: MainWindow,
        result_win: ResultWindow,
        tray: Tray,
        history: HistoryStore,
        parent=None,
    ):
        super().__init__(parent)
        self.config = config
        self.ocr = ocr
        self.main_win = main_win
        self.result_win = result_win
        self.tray = tray
        self.history = history
        self._selecting = False
        self._pending: dict[str, tuple[QPixmap, str]] = {}
        self.selector: ScreenSelector | None = None
        self.hotkey_manager = None

    # ---------- 热键/入口 ----------
    def start_capture(self) -> None:
        if self._selecting:
            return
        self._selecting = True
        self.main_win.hide()
        self.result_win.hide()
        QTimer.singleShot(240, self._show_selector)

    def _show_selector(self) -> None:
        self.selector = ScreenSelector()
        self.selector.selected.connect(self._on_region_selected)
        self.selector.canceled.connect(self._on_selector_canceled)
        self.selector.start()

    def _on_selector_canceled(self) -> None:
        self._selecting = False
        self.selector = None
        self.main_win.show_events()

    def _on_region_selected(self, screen, rect) -> None:
        self._selecting = False
        self.selector = None
        # 等待遮罩撤除、桌面重绘后再截屏
        QTimer.singleShot(150, lambda: self._grab_region_and_ocr(screen, rect))

    def _grab_region_and_ocr(self, screen, rect) -> None:
        pixmap = grab_region(screen, rect)
        if pixmap is None or pixmap.isNull():
            self.tray.showMessage(APP_TITLE, "截图失败，请重试", self.tray.Information, 2500)
            self.main_win.show_events()
            return
        self._process(pixmap, "框选识别")

    def start_fullscreen(self) -> None:
        if self._selecting:
            return
        self.main_win.hide()
        self.result_win.hide()
        QTimer.singleShot(450, self._grab_fullscreen_and_ocr)

    def _grab_fullscreen_and_ocr(self) -> None:
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        pixmap = grab_fullscreen(screen)
        if pixmap is None or pixmap.isNull():
            self.tray.showMessage(APP_TITLE, "全屏截图失败，请重试", self.tray.Information, 2500)
            self.main_win.show_events()
            return
        self._process(pixmap, "全屏扫描")

    def upload_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.main_win,
            "选择要识别的图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp *.gif)",
        )
        if not path:
            return
        img = QImage(path)
        if img.isNull():
            QMessageBox.warning(self.main_win, APP_TITLE, f"无法读取图片文件：\n{path}")
            return
        self._process(QPixmap.fromImage(img), "上传图片")

    # ---------- 识别流程 ----------
    def _process(self, pixmap: QPixmap, mode: str) -> None:
        job = f"{mode}-{uuid.uuid4().hex[:8]}"
        self._pending[job] = (pixmap, mode)
        output = tmp_dir() / f"{job}.png"
        plain = pixmap.copy()
        plain.setDevicePixelRatio(1.0)
        if not plain.save(str(output), "PNG"):
            self._pending.pop(job, None)
            self.tray.showMessage(APP_TITLE, "图片保存失败，无法识别", self.tray.Information, 2500)
            return
        self.main_win.set_busy(f"正在识别（{mode}），请稍候…")
        self.tray.showMessage(APP_TITLE, f"正在识别（{mode}），请稍候…", self.tray.Information, 1500)
        self.ocr.recognize_async(job, str(output))

    def on_ocr_done(self, job: str, items: list[dict]) -> None:
        payload = self._pending.pop(job, None)
        if payload is None:
            return
        pixmap, mode = payload
        text = "\n".join(it["text"] for it in items)
        if text.strip():
            self.history.add(mode, text, pixmap)
            self.main_win.update_history()
        self.result_win.show_result(pixmap, items, mode)
        self.main_win.set_busy(f"识别完成（{mode}）：识别到 {len(items)} 段文字")

    def on_ocr_failed(self, job: str, message: str) -> None:
        self._pending.pop(job, None)
        self.main_win.set_busy("识别失败")
        self.tray.showMessage(APP_TITLE, message, self.tray.Warning, 3500)
        self.main_win.show_events()

    # ---------- 历史 ----------
    def open_history_record(self, rid: str) -> None:
        rec = self.history.get(rid)
        if rec is None:
            return
        image_path = self.history.resolve(rec.get("image", ""))
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            QMessageBox.warning(self.main_win, APP_TITLE, "历史记录的图片已丢失")
            return
        text = rec.get("text", "")
        lines = text.splitlines() if text else None
        self.result_win.show_result(pixmap, [], rec.get("mode", "历史"), text_lines=lines)

    # ---------- 设置 ----------
    def set_hotkey_manager(self, manager) -> None:
        """由 main 注入热键管理器。"""
        self.hotkey_manager = manager

    def open_settings(self) -> None:
        dlg = SettingsDialog(self.config, self._apply_hotkeys, self.main_win)
        if dlg.exec():
            self.main_win.refresh_hints()
            self.tray.update_hint(str(self.config.get("hotkey_capture", "alt+s")))
            self.result_win.ensure_pin()

    def _apply_hotkeys(self, capture: str, fullscreen: str) -> str | None:
        if self.hotkey_manager is None:
            return "热键管理器未初始化"
        return self.hotkey_manager.apply(capture, fullscreen)
