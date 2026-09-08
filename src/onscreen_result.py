"""屏幕上就地结果面板：识别完成后直接在屏幕原位置选文字复制，无需切回主窗口。

对应交互：快捷键 → 框选 → 屏幕原位置出现结果浮层（截图 + 文字高亮框）
→ 点击/拖拽框选文字段 → 底部操作条「复制选中 / 复制全部 / 复制图片 / 详细结果 / 关闭」。
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)


class OnScreenResult(QWidget):
    """覆盖在截图原位置上的可选中结果浮层。"""

    open_detail = Signal()   # 用户点「详细结果」
    closed = Signal()

    def __init__(self, pixmap: QPixmap, items: list[dict], screen, target_rect: QRect,
                 dpr: float = 1.0, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap.copy()
        self._pixmap.setDevicePixelRatio(1.0)
        self._items = items or []
        self._screen = screen
        self._selected: set[int] = set()
        self._hover: int | None = None
        self._band: QRect | None = None
        self._band_start: QPoint | None = None
        self._status = ""

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setCursor(Qt.ArrowCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        # 面板几何：优先贴合原框选位置，超出屏幕时居中缩放
        geo = target_rect if target_rect is not None and not target_rect.isEmpty() else None
        if geo is None and screen is not None:
            geo = screen.geometry()
        if geo is None:
            geo = QRect(100, 100, self._pixmap.width(), self._pixmap.height())
        scr_geo = screen.geometry() if screen is not None else geo
        if geo.width() > scr_geo.width() or geo.height() > scr_geo.height():
            w = min(geo.width(), scr_geo.width() - 40)
            h = min(geo.height(), scr_geo.height() - 40)
            geo = QRect(scr_geo.x() + (scr_geo.width() - w) // 2,
                        scr_geo.y() + (scr_geo.height() - h) // 2, w, h)
        self.setGeometry(geo)

        # 物理像素 → 面板坐标的缩放系数
        self._scale = (self.width() / self._pixmap.width()) if self._pixmap.width() else 1.0
        self._dpr = dpr or 1.0

        self._build_toolbar()
        self._layout_toolbar()

    # ---------- 操作条 ----------
    def _build_toolbar(self) -> None:
        self.toolbar = QWidget(self)
        self.toolbar.setStyleSheet(
            "background: rgba(28, 42, 60, 232); border-radius: 10px;"
        )
        lay = QHBoxLayout(self.toolbar)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)

        self.label_hint = QLabel("点击或拖拽框选文字")
        self.label_hint.setStyleSheet("color: #BFE0F8; background: transparent;")
        lay.addWidget(self.label_hint)

        self.btn_copy_sel = QPushButton("复制选中")
        self.btn_copy_sel.clicked.connect(self.copy_selected)
        self.btn_copy_all = QPushButton("复制全部")
        self.btn_copy_all.clicked.connect(self.copy_all)
        self.btn_copy_img = QPushButton("复制图片")
        self.btn_copy_img.clicked.connect(self.copy_image)
        self.btn_detail = QPushButton("详细结果")
        self.btn_detail.clicked.connect(self.open_detail.emit)
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.close)
        for b in (self.btn_copy_sel, self.btn_copy_all, self.btn_copy_img,
                  self.btn_detail, self.btn_close):
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                "QPushButton { background: #2F80D6; color: white; border: none;"
                " border-radius: 7px; padding: 6px 12px; }"
                "QPushButton:hover { background: #2A6FB8; }"
            )
            lay.addWidget(b)

    def _layout_toolbar(self) -> None:
        self.toolbar.adjustSize()
        w = self.toolbar.width()
        h = self.toolbar.height()
        x = max(8, (self.width() - w) // 2)
        y = max(8, self.height() - h - 12)
        self.toolbar.move(x, y)
        self.toolbar.raise_()

    # ---------- 绘制 ----------
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawPixmap(self.rect(), self._pixmap)

        for idx, it in enumerate(self._items):
            box = it.get("box") or []
            if len(box) < 4:
                continue
            poly = QPolygonF([self._to_panel(pt) for pt in box])
            if idx in self._selected:
                p.setPen(QPen(QColor(47, 128, 214, 255), 2))
                p.setBrush(QColor(47, 128, 214, 110))
            elif idx == self._hover:
                p.setPen(QPen(QColor(47, 128, 214, 220), 2))
                p.setBrush(QColor(47, 128, 214, 55))
            else:
                p.setPen(QPen(QColor(47, 128, 214, 120), 1))
                p.setBrush(QColor(255, 255, 255, 30))
            p.drawPolygon(poly)

        if self._band is not None:
            p.setPen(QPen(QColor(47, 128, 214, 255), 2, Qt.DashLine))
            p.setBrush(QColor(74, 144, 226, 40))
            p.drawRect(self._band)

        # 外边框
        p.setPen(QPen(QColor(47, 128, 214, 200), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(self.rect().adjusted(1, 1, -2, -2))
        p.end()

    def _to_panel(self, pt) -> QPoint:
        return QPoint(int(pt[0] * self._scale), int(pt[1] * self._scale))

    def _hit(self, pos: QPoint) -> int | None:
        for idx, it in enumerate(self._items):
            box = it.get("box") or []
            if len(box) < 4:
                continue
            if QPolygonF([self._to_panel(pt) for pt in box]).containsPoint(pos, Qt.OddEvenFill):
                return idx
        return None

    # ---------- 鼠标 ----------
    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        pos = ev.position().toPoint()
        hit = self._hit(pos)
        if hit is not None:
            if ev.modifiers() & Qt.ControlModifier:
                self._selected.symmetric_difference_update({hit})
            else:
                if hit in self._selected and len(self._selected) == 1:
                    self._selected.clear()
                else:
                    self._selected = {hit}
            self._update_status()
            self.update()
            return
        # 空白处：开始框选
        if not (ev.modifiers() & Qt.ControlModifier):
            self._selected.clear()
        self._band_start = pos
        self._band = QRect(pos, pos)
        self.update()

    def mouseMoveEvent(self, ev):
        pos = ev.position().toPoint()
        if self._band_start is not None:
            self._band = QRect(self._band_start, pos).normalized()
            self.update()
            return
        hover = self._hit(pos)
        if hover != self._hover:
            self._hover = hover
            self.update()

    def mouseReleaseEvent(self, ev):
        if ev.button() != Qt.LeftButton or self._band_start is None:
            return
        band = QRect(self._band_start, ev.position().toPoint()).normalized()
        self._band_start = None
        self._band = None
        if band.width() < 4 and band.height() < 4:
            self.update()
            return
        for idx, it in enumerate(self._items):
            box = it.get("box") or []
            if len(box) < 4:
                continue
            poly = QPolygonF([self._to_panel(pt) for pt in box])
            if poly.boundingRect().intersects(band):
                self._selected.add(idx)
        self._update_status()
        self.update()

    # ---------- 键盘 ----------
    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.close()
            return
        if ev.key() == Qt.Key_A and (ev.modifiers() & Qt.ControlModifier):
            self._selected = set(range(len(self._items)))
            self._update_status()
            self.update()
            return
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.copy_selected()
            return
        super().keyPressEvent(ev)

    # ---------- 操作 ----------
    def _update_status(self) -> None:
        n = len(self._selected)
        self.label_hint.setText(f"已选 {n} 段文字" if n else "点击或拖拽框选文字")
        self.btn_copy_sel.setText(f"复制选中（{n}）" if n else "复制选中")
        self._layout_toolbar()

    def selected_text(self) -> str:
        return "\n".join(
            self._items[i]["text"] for i in sorted(self._selected)
            if i < len(self._items)
        )

    def copy_selected(self) -> None:
        text = self.selected_text()
        if not text:
            self.label_hint.setText("请先点击或框选要复制的文字")
            self._layout_toolbar()
            return
        QGuiApplication.clipboard().setText(text)
        self.label_hint.setText(f"已复制 {len(self._selected)} 段文字 ✓")
        self._layout_toolbar()

    def copy_all(self) -> None:
        text = "\n".join(it["text"] for it in self._items if str(it.get("text", "")).strip())
        if not text:
            self.label_hint.setText("未识别到文字")
            self._layout_toolbar()
            return
        QGuiApplication.clipboard().setText(text)
        self.label_hint.setText("已复制全部文字 ✓")
        self._layout_toolbar()

    def copy_image(self) -> None:
        QGuiApplication.clipboard().setImage(self._pixmap.toImage())
        self.label_hint.setText("已复制图片 ✓")
        self._layout_toolbar()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._scale = (self.width() / self._pixmap.width()) if self._pixmap.width() else 1.0
        self._layout_toolbar()

    def showEvent(self, ev):
        super().showEvent(ev)
        self._layout_toolbar()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def closeEvent(self, ev):
        self.closed.emit()
        super().closeEvent(ev)
