"""应用主控制：串联热键、截图、OCR、结果窗、历史、设置。"""
from __future__ import annotations

import logging
import uuid

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import QFileDialog, QMessageBox, QSystemTrayIcon

from . import autostart
from .capture import grab_fullscreen, grab_region
from .config import APP_TITLE, Config, tmp_dir
from .history import HistoryStore
from .main_window import MainWindow
from .ocr_engine import OcrEngine
from .onscreen_result import OnScreenResult
from .overlay import ScreenSelector
from .result_window import ResultWindow
from .settings_window import SettingsDialog
from .tray import Tray

log = logging.getLogger("app")


def _notify(tray: Tray, message: str, warning: bool = False) -> None:
    """托盘气泡通知；任何通知异常不得影响主流程。"""
    try:
        icon = QSystemTrayIcon.Warning if warning else QSystemTrayIcon.Information
        tray.showMessage(APP_TITLE, message, icon, 3000)
    except Exception as e:  # noqa: BLE001
        log.exception("托盘通知失败（忽略）: %s", e)


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
        self._pending: dict[str, tuple] = {}
        self.selector: ScreenSelector | None = None
        self.onscreen: OnScreenResult | None = None
        self._onscreen_job: str | None = None
        self.hotkey_manager = None

    # ---------- 热键/入口 ----------
    def start_capture(self) -> None:
        if self._selecting:
            return
        self._close_onscreen()
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
            _notify(self.tray, "截图失败，请重试")
            self.main_win.show_events()
            return
        self._process(pixmap, "框选识别", screen=screen, rect=rect)

    def start_fullscreen(self) -> None:
        if self._selecting:
            return
        self._close_onscreen()
        self.main_win.hide()
        self.result_win.hide()
        QTimer.singleShot(450, self._grab_fullscreen_and_ocr)

    def _close_onscreen(self) -> None:
        if self.onscreen is not None:
            try:
                self.onscreen.close()
            except Exception:  # noqa: BLE001
                pass
            self.onscreen = None
        self._onscreen_job = None

    def _grab_fullscreen_and_ocr(self) -> None:
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        pixmap = grab_fullscreen(screen)
        if pixmap is None or pixmap.isNull():
            _notify(self.tray, "全屏截图失败，请重试")
            self.main_win.show_events()
            return
        self._process(pixmap, "全屏扫描", screen=screen, rect=screen.geometry())

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
    def _process(self, pixmap: QPixmap, mode: str, screen=None, rect=None) -> None:
        job = f"{mode}-{uuid.uuid4().hex[:8]}"
        self._pending[job] = (pixmap, mode, screen, rect)
        output = tmp_dir() / f"{job}.png"
        plain = pixmap.copy()
        plain.setDevicePixelRatio(1.0)
        if not plain.save(str(output), "PNG"):
            self._pending.pop(job, None)
            _notify(self.tray, "图片保存失败，无法识别")
            return
        # 截图类识别：先把截图留在前台（占位面板 + 正在识别），识别完成后原地升级
        if screen is not None:
            self._show_processing_panel(pixmap, screen, rect)
            self._onscreen_job = job
        self.main_win.set_busy(f"正在识别（{mode}），请稍候…")
        _notify(self.tray, f"正在识别（{mode}），请稍候…")
        log.info("发起识别 job=%s mode=%s 图片=%s", job, mode, output)
        self.ocr.recognize_async(job, str(output))

    def on_ocr_done(self, job: str, items: list[dict]) -> None:
        log.info("识别完成回调 job=%s 项数=%d", job, len(items))
        payload = self._pending.pop(job, None)
        if payload is None:
            log.warning("识别完成但无对应任务 job=%s", job)
            return
        pixmap, mode = payload[0], payload[1]
        screen = payload[2] if len(payload) > 2 else None
        rect = payload[3] if len(payload) > 3 else None
        text = "\n".join(it["text"] for it in items)
        try:
            if text.strip():
                self.history.add(mode, text, pixmap)
                self.main_win.update_history()
            if screen is not None and self.onscreen is not None and self._onscreen_job == job:
                # 占位面板还在：原地升级为可交互结果（截图始终留在前台）
                self.onscreen.apply_result(items)
                log.info("占位面板已升级为结果 job=%s", job)
            elif screen is not None and self.onscreen is not None:
                # 已有其他面板（理论上不会发生）：替换
                self._show_onscreen(pixmap, items, screen, rect, mode)
            elif screen is not None:
                # 用户在处理过程中关掉了面板：不再打扰，结果已存入历史
                log.info("面板已被用户关闭，跳过展示 job=%s", job)
            else:
                self.result_win.show_result(pixmap, items, mode)
        except Exception:  # noqa: BLE001
            log.exception("结果展示环节异常 job=%s", job)
        self.main_win.set_busy(f"识别完成（{mode}）：识别到 {len(items)} 段文字")
        log.info("结果已展示 job=%s 屏幕浮层=%s", job, screen is not None)

    def _show_processing_panel(self, pixmap: QPixmap, screen, rect) -> None:
        """框选完成后立刻把截图留在前台，显示「正在识别…」。"""
        self._close_onscreen()
        dpr = screen.devicePixelRatio() or 1.0
        panel = OnScreenResult(pixmap, [], screen, rect, dpr=dpr, processing=True)
        panel.open_detail.connect(self._open_detail_from_panel)
        panel.closed.connect(self._on_onscreen_closed)
        panel.show()
        self.onscreen = panel
        log.info("占位面板已显示（正在识别）rect=%s", rect)

    def _open_detail_from_panel(self) -> None:
        """浮层点「详细结果」：用面板当前的图片与结果打开结果窗。"""
        panel = self.onscreen
        if panel is None:
            return
        self.result_win.show_result(panel.pixmap(), panel.items(), "框选识别")

    def _show_onscreen(self, pixmap: QPixmap, items: list[dict], screen, rect, mode: str) -> None:
        """在截图原位置弹出可选中结果的浮层。"""
        if self.onscreen is not None:
            try:
                self.onscreen.close()
            except Exception:  # noqa: BLE001
                pass
            self.onscreen = None
        dpr = screen.devicePixelRatio() or 1.0
        panel = OnScreenResult(pixmap, items, screen, rect, dpr=dpr)
        panel.open_detail.connect(
            lambda: self.result_win.show_result(pixmap, items, mode)
        )
        panel.closed.connect(self._on_onscreen_closed)
        panel.show()
        self.onscreen = panel
        log.info("屏幕浮层已显示 items=%d rect=%s", len(items), rect)

    def _on_onscreen_closed(self) -> None:
        self.onscreen = None
        self._onscreen_job = None

    def on_ocr_failed(self, job: str, message: str) -> None:
        log.warning("识别失败回调 job=%s: %s", job, message)
        self._pending.pop(job, None)
        self.main_win.set_busy("识别失败")
        _notify(self.tray, message, warning=True)
        if self.onscreen is not None and self._onscreen_job == job:
            # 占位面板还在：原地面板提示失败，不再弹窗打扰
            self.onscreen.apply_error("识别失败，请重试")
            return
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
