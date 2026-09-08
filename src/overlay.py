"""屏幕框选罩层：每个屏幕一个半透明遮罩，拖拽框选后回传区域。"""
from __future__ import annotations

from PySide6.QtCore import QObject, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen, QScreen
from PySide6.QtWidgets import QWidget

MIN_SIZE = 6          # 小于该尺寸视为误触
HINT = "按住鼠标左键拖动，框选要识别的区域 —— 松开自动识别    |    Esc 或 右键 取消"


class OverlayWindow(QWidget):
    """单个屏幕上的全屏遮罩。"""

    selected = Signal(object, QRect)   # (QScreen, QRect 相对屏幕左上角, 逻辑坐标)
    canceled = Signal()

    def __init__(self, screen: QScreen):
        super().__init__()
        self.screen_ref = screen
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setGeometry(screen.geometry())
        self._start: QRect | None = None   # 拖拽起点(局部逻辑坐标)
        self._current: QRect | None = None  # 当前选区
        self._mouse_pos = None
        self._active = True

    # ---------- 鼠标 ----------
    def mousePressEvent(self, ev):
        if ev.button() == Qt.RightButton:
            self.canceled.emit()
            return
        if ev.button() == Qt.LeftButton:
            self._start = QRect(ev.position().toPoint(), QSize(0, 0))
            self._current = None
            self.update()

    def mouseMoveEvent(self, ev):
        if self._start is None:
            self._mouse_pos = ev.position().toPoint()
        else:
            self._current = self._clip(self._start, ev.position().toPoint())
        self.update()

    def mouseReleaseEvent(self, ev):
        if ev.button() != Qt.LeftButton or self._start is None:
            return
        rect = self._clip(self._start, ev.position().toPoint())
        self._start = None
        if rect.width() < MIN_SIZE or rect.height() < MIN_SIZE:
            self._current = None
            self.update()
            return
        self.selected.emit(self.screen_ref, rect)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.canceled.emit()
            return
        super().keyPressEvent(ev)

    # ---------- 选区裁剪：限制在本屏幕内 ----------
    def _clip(self, p1, p2) -> QRect:
        geo = self.screen_ref.geometry()
        x1, y1 = p1.x(), p1.y()
        x2, y2 = p2.x(), p2.y()
        x = min(x1, x2)
        y = min(y1, y2)
        w = abs(x2 - x1)
        h = abs(y2 - y1)
        x = max(0, min(x, geo.width() - 1))
        y = max(0, min(y, geo.height() - 1))
        w = max(1, min(w, geo.width() - x))
        h = max(1, min(h, geo.height() - y))
        return QRect(x, y, w, h)

    # ---------- 绘制 ----------
    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # 暗色遮罩
        painter.fillRect(self.rect(), QColor(10, 30, 55, 95))
        # 顶部提示
        font = QFont("Microsoft YaHei UI", 11)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        tw = painter.fontMetrics().horizontalAdvance(HINT)
        rect = self.screen_ref.geometry()
        tx = max(10, (rect.width() - tw) // 2)
        painter.drawText(tx, 18, HINT)
        # 十字线 + 选区
        if self._current is not None:
            r = self._current
            painter.setPen(QPen(QColor(47, 128, 214, 255), 2))
            painter.setBrush(QColor(74, 144, 226, 36))
            painter.drawRect(r)
            painter.setPen(QPen(QColor(255, 255, 255, 230), 1))
            painter.drawText(r.x() + 4, r.y() - 4, f"{r.width()} × {r.height()}")
        elif self._mouse_pos is not None:
            c = self._mouse_pos
            painter.setPen(QPen(QColor(255, 255, 255, 120), 1))
            painter.drawLine(c.x(), 0, c.x(), self.height())
            painter.drawLine(0, c.y(), self.width(), c.y())
        painter.end()

    def set_active(self, active: bool) -> None:
        self._active = active


class ScreenSelector(QObject):
    """所有屏幕一起放罩层；选中或取消后统一清理。"""

    selected = Signal(object, QRect)   # (QScreen, QRect)
    canceled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._overlays: list[OverlayWindow] = []
        self._done = False

    def start(self) -> None:
        for screen in QGuiApplication.screens():
            ov = OverlayWindow(screen)
            ov.selected.connect(self._on_selected)
            ov.canceled.connect(self._on_canceled)
            ov.show()
            ov.raise_()
            ov.activateWindow()
            self._overlays.append(ov)

    def _cleanup(self) -> None:
        for ov in self._overlays:
            ov.hide()
            ov.deleteLater()
        self._overlays = []

    def _on_selected(self, screen: QScreen, rect: QRect) -> None:
        if self._done:
            return
        self._done = True
        self._cleanup()
        self.selected.emit(screen, rect)

    def _on_canceled(self) -> None:
        if self._done:
            return
        self._done = True
        self._cleanup()
        self.canceled.emit()

    def cancel(self) -> None:
        self._on_canceled()
