"""截图与图像工具。"""
from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtGui import QPixmap


def _physical_pixmap(screen) -> QPixmap | None:
    """截取整个屏幕，返回物理像素 pixmap（devicePixelRatio 置 1）。"""
    try:
        full = screen.grabWindow(0)
    except Exception:
        return None
    if full is None or full.isNull():
        return None
    full = full.copy()
    full.setDevicePixelRatio(1.0)
    return full


def grab_region(screen, rect: QRect) -> QPixmap | None:
    """截取某屏幕上逻辑坐标 rect 区域（rect 相对屏幕左上角，设备无关像素）。

    返回物理像素 pixmap（dpr=1），保证与 OCR 坐标一致。
    """
    full = _physical_pixmap(screen)
    if full is None:
        return None
    dpr = screen.devicePixelRatio() or 1.0
    x = max(0, int(round(rect.x() * dpr)))
    y = max(0, int(round(rect.y() * dpr)))
    w = max(1, min(int(round(rect.width() * dpr)), full.width() - x))
    h = max(1, min(int(round(rect.height() * dpr)), full.height() - y))
    return full.copy(x, y, w, h)


def grab_fullscreen(screen) -> QPixmap | None:
    """截取整个屏幕（物理像素，dpr=1）。"""
    return _physical_pixmap(screen)


def draw_boxes(pixmap: QPixmap, items: list[dict]) -> QPixmap:
    """在图片副本上画出识别框（蓝色半透明），用于结果预览。"""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

    out = pixmap.copy()
    out.setDevicePixelRatio(1.0)
    painter = QPainter(out)
    pen = QPen(QColor(47, 128, 214, 230), 2)
    brush = QColor(47, 128, 214, 28)
    painter.setPen(pen)
    painter.setBrush(brush)
    for it in items:
        box = it.get("box") or []
        if len(box) < 4:
            continue
        poly = QPolygonF([QPointF(p[0], p[1]) for p in box])
        painter.drawPolygon(poly)
    painter.end()
    return out


def pixmap_to_png_bytes(pixmap: QPixmap) -> bytes:
    """pixmap → png 字节（dpr 归一为 1）。"""
    from PySide6.QtCore import QBuffer, QIODevice

    plain = pixmap.copy()
    plain.setDevicePixelRatio(1.0)
    ba = QBuffer()
    ba.open(QIODevice.WriteOnly)
    plain.save(ba, "PNG")
    ba.close()
    return bytes(ba.data())
