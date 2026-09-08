"""可视化校验：真实截屏 → OCR → 渲染屏幕浮层，输出 PNG 供人眼确认框与文字对齐。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from src.capture import grab_region
from src.config import tmp_dir
from src.ocr_engine import OcrEngine
from src.onscreen_result import OnScreenResult
from src.theme import apply_theme

OUT = Path(__file__).parent.parent / "tests" / "_artifacts"


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)
    screen = QGuiApplication.primaryScreen()
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 900
    h = int(sys.argv[2]) if len(sys.argv) > 2 else 260
    rect = QRect(80, 80, w, h)
    pm = grab_region(screen, rect)
    assert pm is not None and not pm.isNull(), "截图失败"
    path = tmp_dir() / "align_check.png"
    plain = pm.copy()
    plain.setDevicePixelRatio(1.0)
    plain.save(str(path), "PNG")

    engine = OcrEngine()
    items = engine.recognize_sync(str(path))
    print(f"识别 {len(items)} 项；图片 {pm.width()}x{pm.height()}（逻辑区域 {rect.width()}x{rect.height()}）")

    panel = OnScreenResult(pm, items, screen, rect, dpr=screen.devicePixelRatio() or 1.0)
    panel.show()
    panel._selected = set(range(len(items)))   # 全部高亮，便于核对框与文字对齐
    panel._update_status()
    app.processEvents()
    print(f"面板 {panel.width()}x{panel.height()}  绘制区 {panel._draw_rect}  scale={panel._scale:.4f}")
    OUT.mkdir(parents=True, exist_ok=True)
    grab = panel.grab()
    out = OUT / "alignment_render.png"
    grab.save(str(out), "PNG")
    # 再存一张左上角局部放大图（2 倍）便于细看
    crop = grab.copy(0, 0, min(900, grab.width()), min(300, grab.height()))
    crop.scaled(crop.width() * 2, crop.height() * 2).save(
        str(OUT / "alignment_zoom.png"), "PNG"
    )
    panel.close()
    print(f"已保存：{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
