"""通用控件：图片预览（支持子区域框选）、应用图标生成。"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy


class ImageArea(QLabel):
    """等比缩放居中显示一张图片；支持开启「框选模式」在原图上拖选子区域。

    框选结果以「原图坐标系」的 QRect 发出。
    """

    rect_selected = Signal(QRect)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source: QPixmap | None = None
        self._display_rect = QRect()          # 图在控件内的显示区域
        self._sel_mode = False
        self._drag_start = None
        self._drag_rect = None
        self.setMinimumSize(200, 160)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setObjectName("ImageArea")   # 背景/边框由主题样式表控制

    # ---------- 数据 ----------
    def set_source(self, pm: QPixmap | None) -> None:
        self._source = pm
        self.set_selection_mode(False)
        self.update()

    def source(self) -> QPixmap | None:
        return self._source

    def set_selection_mode(self, on: bool) -> None:
        self._sel_mode = on
        self.setCursor(Qt.CrossCursor if on else Qt.ArrowCursor)
        if on:
            self.setToolTip("按住鼠标左键拖动，框选要提取的图片区域")
        else:
            self.setToolTip("")
        self.update()

    @property
    def selection_mode(self) -> bool:
        return self._sel_mode

    # ---------- 绘制 ----------
    def _fit_rect(self) -> QRect:
        if self._source is None:
            return QRect()
        sw, sh = self._source.width(), self._source.height()
        if sw <= 0 or sh <= 0:
            return QRect()
        scale = min(self.width() / sw, self.height() / sh)
        dw, dh = max(1, int(sw * scale)), max(1, int(sh * scale))
        x = (self.width() - dw) // 2
        y = (self.height() - dh) // 2
        return QRect(x, y, dw, dh)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if self._source is None or self._source.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        target = self._fit_rect()
        self._display_rect = target
        painter.drawPixmap(target, self._source)
        if self._sel_mode and self._drag_rect is not None:
            painter.setPen(QPen(QColor(47, 128, 214, 255), 2))
            painter.setBrush(QColor(74, 144, 226, 32))
            painter.drawRect(self._drag_rect & target)
        painter.end()

    def resizeEvent(self, ev):
        self.update()
        super().resizeEvent(ev)

    # ---------- 框选 ----------
    def mousePressEvent(self, ev):
        if self._sel_mode and ev.button() == Qt.LeftButton:
            self._drag_start = ev.position().toPoint()
            self._drag_rect = QRect(self._drag_start, QSize(0, 0))
            self.update()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._sel_mode and self._drag_start is not None:
            p = ev.position().toPoint()
            self._drag_rect = QRect(
                min(self._drag_start.x(), p.x()),
                min(self._drag_start.y(), p.y()),
                abs(p.x() - self._drag_start.x()),
                abs(p.y() - self._drag_start.y()),
            )
            self.update()
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._sel_mode and ev.button() == Qt.LeftButton and self._drag_start is not None:
            p = ev.position().toPoint()
            rect = QRect(
                min(self._drag_start.x(), p.x()),
                min(self._drag_start.y(), p.y()),
                abs(p.x() - self._drag_start.x()),
                abs(p.y() - self._drag_start.y()),
            )
            self._drag_start = None
            self._drag_rect = None
            self.update()
            if self._source is None or self._display_rect.isEmpty():
                return
            if rect.width() < 4 or rect.height() < 4:
                return
            src = self._map_to_source(rect)
            if src is not None:
                self.rect_selected.emit(src)
            return
        super().mouseReleaseEvent(ev)

    def _map_to_source(self, widget_rect: QRect) -> QRect | None:
        """控件坐标区域 → 原图坐标区域。"""
        if self._source is None or self._display_rect.width() <= 0:
            return None
        dr = self._display_rect
        dx = (widget_rect.x() - dr.x()) * self._source.width() / dr.width()
        dy = (widget_rect.y() - dr.y()) * self._source.height() / dr.height()
        dw = widget_rect.width() * self._source.width() / dr.width()
        dh = widget_rect.height() * self._source.height() / dr.height()
        x = max(0, min(int(round(dx)), self._source.width() - 1))
        y = max(0, min(int(round(dy)), self._source.height() - 1))
        w = max(1, min(int(round(dw)), self._source.width() - x))
        h = max(1, min(int(round(dh)), self._source.height() - y))
        return QRect(x, y, w, h)


def make_app_icon(size: int = 256) -> QIcon:
    """绘制应用图标：淡蓝圆角底 + 白色放大镜（内嵌文字识别含义）。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    # 圆角底
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#2F80D6"))
    radius = int(size * 0.22)
    p.drawRoundedRect(0, 0, size, size, radius, radius)
    # 放大镜：圆环 + 手柄
    ring_w = int(size * 0.16)
    cx, cy = int(size * 0.44), int(size * 0.44)
    r = int(size * 0.20)
    pen = QPen(QColor("white"), ring_w)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.drawEllipse(cx, cy, r, r)
    pen2 = QPen(QColor("white"), int(size * 0.13))
    pen2.setCapStyle(Qt.RoundCap)
    p.setPen(pen2)
    p.drawLine(QPointF(cx + r * 0.72, cy + r * 0.72), QPointF(size * 0.80, size * 0.80))
    p.end()
    return QIcon(pm)


def make_app_icon_pixmap(size: int = 256) -> QPixmap:
    return make_app_icon(size).pixmap(size, size)
