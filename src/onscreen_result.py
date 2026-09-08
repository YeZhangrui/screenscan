"""屏幕上就地结果面板：识别完成后直接在屏幕原位置选文字复制，无需切回主窗口。

交互：快捷键 → 框选 → 屏幕原位置出现结果浮层（截图 + 文字高亮框）
→ 点击/拖拽框选文字段 → 操作条「复制选中 / 复制全部 / 复制图片 / 详细结果 / 关闭」。

注意：操作条是**独立的置顶窗口**，位置在框选区域**外面**（下方优先、上方兜底），
这样即使识别区域很小，也不会遮住文字、也能随时关闭。
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

MIN_PANEL_W = 380   # 面板最小显示宽度（过小区域会自动放大，便于点选）
MIN_PANEL_H = 170
BAR_MARGIN = 8      # 操作条与面板的间距
RADIUS = 10         # 圆角半径（面板与操作条保持一致）


class OnScreenToolbar(QWidget):
    """独立置顶操作条（位于框选区域外）。"""

    def __init__(self, owner: "OnScreenResult"):
        super().__init__(None)
        self._owner = owner
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        # 透明窗口背景：圆角之外不出现白色方角
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        bar = QWidget()
        bar.setObjectName("Bar")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        bar.setStyleSheet(
            "QWidget#Bar { background: rgba(28, 42, 60, 238);"
            f" border-radius: {RADIUS}px; }}"
        )
        outer.addWidget(bar)

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)

        self.label_hint = QLabel("点击或拖拽框选文字")
        self.label_hint.setStyleSheet("color: #BFE0F8; background: transparent;")
        lay.addWidget(self.label_hint)

        self.btn_copy_sel = QPushButton("复制选中")
        self.btn_copy_sel.clicked.connect(owner.copy_selected)
        self.btn_copy_all = QPushButton("复制全部")
        self.btn_copy_all.clicked.connect(owner.copy_all)
        self.btn_copy_img = QPushButton("复制图片")
        self.btn_copy_img.clicked.connect(owner.copy_image)
        self.btn_detail = QPushButton("详细结果")
        self.btn_detail.clicked.connect(owner.open_detail.emit)
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(owner.close)
        for b in (self.btn_copy_sel, self.btn_copy_all, self.btn_copy_img,
                  self.btn_detail, self.btn_close):
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)   # 焦点留在面板上，Esc 始终有效
            b.setStyleSheet(
                "QPushButton { background: #2F80D6; color: white; border: none;"
                " border-radius: 7px; padding: 6px 12px; }"
                "QPushButton:hover { background: #2A6FB8; }"
            )
            lay.addWidget(b)


class OnScreenResult(QWidget):
    """覆盖在截图原位置上的可选中结果浮层。"""

    open_detail = Signal()
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

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        # 透明窗口背景 + 圆角绘制，与操作条曲率一致，避免方角违和
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.ArrowCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        scr_geo = screen.geometry() if screen is not None else QRect(0, 0, 1920, 1080)
        geo = target_rect if target_rect is not None and not target_rect.isEmpty() else scr_geo
        # 先保证不超出屏幕
        w = min(geo.width(), scr_geo.width())
        h = min(geo.height(), scr_geo.height())
        x = max(scr_geo.x(), min(geo.x(), scr_geo.x() + scr_geo.width() - w))
        y = max(scr_geo.y(), min(geo.y(), scr_geo.y() + scr_geo.height() - h))
        # 区域过小时放大到最小可用尺寸，但**保持原始宽高比**（否则文字与识别框会错位）
        if w < MIN_PANEL_W or h < MIN_PANEL_H:
            k = max(MIN_PANEL_W / w, MIN_PANEL_H / h)
            k = min(k, scr_geo.width() / w, scr_geo.height() / h)
            w = int(round(w * k))
            h = int(round(h * k))
        w = min(w, scr_geo.width())
        h = min(h, scr_geo.height())
        x = max(scr_geo.x(), min(x, scr_geo.x() + scr_geo.width() - w))
        y = max(scr_geo.y(), min(y, scr_geo.y() + scr_geo.height() - h))
        self.setGeometry(QRect(x, y, w, h))

        # 物理像素 → 面板坐标：等比缩放（绘制区域与命中检测共用同一映射）
        self._draw_rect = self._fit_rect()
        self._scale = (
            self._draw_rect.width() / self._pixmap.width()
            if self._pixmap.width() else 1.0
        )
        self._dpr = dpr or 1.0

        self.toolbar = OnScreenToolbar(self)
        self._update_status()

    # ---------- 操作条位置：始终在面板外面 ----------
    def _layout_toolbar(self) -> None:
        self.toolbar.adjustSize()
        tw, th = self.toolbar.width(), self.toolbar.height()
        scr = self._screen.geometry() if self._screen is not None else self.geometry()

        x = self.geometry().center().x() - tw // 2
        x = max(scr.x() + BAR_MARGIN, min(x, scr.x() + scr.width() - tw - BAR_MARGIN))

        below = self.geometry().bottom() + BAR_MARGIN
        above = self.geometry().top() - th - BAR_MARGIN
        if below + th <= scr.y() + scr.height() - BAR_MARGIN:
            y = below                      # 下方优先
        elif above >= scr.y() + BAR_MARGIN:
            y = above                      # 下方不够 → 放上方
        else:
            # 上下都放不下（极端情况）：贴在屏幕底部，且尽量不遮面板
            y = scr.y() + scr.height() - th - BAR_MARGIN
        self.toolbar.setGeometry(QRect(x, y, tw, th))
        self.toolbar.raise_()

    # ---------- 绘制 ----------
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        # 圆角裁剪：面板四角透明，曲率与操作条一致
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0), RADIUS, RADIUS
        )
        p.setClipPath(path)

        p.drawPixmap(self._draw_rect, self._pixmap)

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

        # 圆角边框（解除裁剪后绘制，保证描边完整）
        p.setClipping(False)
        p.setPen(QPen(QColor(47, 128, 214, 200), 2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(
            QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0), RADIUS, RADIUS
        )
        p.end()

    # ---------- 坐标映射 ----------
    def _fit_rect(self) -> QRect:
        """图片在面板内的绘制区域：等比缩放并居中（保证不拉伸变形）。"""
        pw, ph = self._pixmap.width(), self._pixmap.height()
        if pw <= 0 or ph <= 0:
            return self.rect()
        s = min(self.width() / pw, self.height() / ph)
        dw, dh = max(1, int(round(pw * s))), max(1, int(round(ph * s)))
        return QRect((self.width() - dw) // 2, (self.height() - dh) // 2, dw, dh)

    def _to_panel(self, pt) -> QPoint:
        dr = self._draw_rect
        return QPoint(
            int(round(dr.x() + pt[0] * self._scale)),
            int(round(dr.y() + pt[1] * self._scale)),
        )

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
        self.toolbar.label_hint.setText(f"已选 {n} 段文字" if n else "点击或拖拽框选文字")
        self.toolbar.btn_copy_sel.setText(f"复制选中（{n}）" if n else "复制选中")
        self._layout_toolbar()

    def selected_text(self) -> str:
        return "\n".join(
            self._items[i]["text"] for i in sorted(self._selected)
            if i < len(self._items)
        )

    def copy_selected(self) -> None:
        text = self.selected_text()
        if not text:
            self.toolbar.label_hint.setText("请先点击或框选要复制的文字")
            self._layout_toolbar()
            return
        QGuiApplication.clipboard().setText(text)
        self.toolbar.label_hint.setText(f"已复制 {len(self._selected)} 段文字 ✓")
        self._layout_toolbar()

    def copy_all(self) -> None:
        text = "\n".join(it["text"] for it in self._items if str(it.get("text", "")).strip())
        if not text:
            self.toolbar.label_hint.setText("未识别到文字")
            self._layout_toolbar()
            return
        QGuiApplication.clipboard().setText(text)
        self.toolbar.label_hint.setText("已复制全部文字 ✓")
        self._layout_toolbar()

    def copy_image(self) -> None:
        QGuiApplication.clipboard().setImage(self._pixmap.toImage())
        self.toolbar.label_hint.setText("已复制图片 ✓")
        self._layout_toolbar()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._draw_rect = self._fit_rect()
        self._scale = (
            self._draw_rect.width() / self._pixmap.width()
            if self._pixmap.width() else 1.0
        )
        self._layout_toolbar()

    def showEvent(self, ev):
        super().showEvent(ev)
        self.toolbar.show()
        self._layout_toolbar()
        self.raise_()
        self.toolbar.raise_()
        self.activateWindow()
        self.setFocus()

    def closeEvent(self, ev):
        try:
            self.toolbar.close()
        except Exception:  # noqa: BLE001
            pass
        self.closed.emit()
        super().closeEvent(ev)
