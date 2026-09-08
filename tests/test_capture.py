"""真实截屏测试：验证 QScreen.grabWindow 与 DPR 坐标换算。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from src.capture import grab_fullscreen, grab_region


def main() -> int:
    app = QApplication(sys.argv)  # noqa: F841
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        print("FAIL：无屏幕")
        return 1
    geo = screen.geometry()
    dpr = screen.devicePixelRatio() or 1.0
    print(f"屏幕几何：{geo.width()}x{geo.height()}  dpr={dpr}")

    full = grab_fullscreen(screen)
    if full is None or full.isNull():
        print("FAIL：整屏截图失败")
        return 1
    print(f"整屏物理像素：{full.width()}x{full.height()}")
    ok_full = full.width() >= int(geo.width() * dpr) * 0.9
    if not ok_full:
        print(f"FAIL：整屏尺寸异常（期望约 {geo.width() * dpr:.0f}x{geo.height() * dpr:.0f}）")
        return 1

    rect = QRect(0, 0, 200, 120)
    region = grab_region(screen, rect)
    if region is None or region.isNull():
        print("FAIL：区域截图失败")
        return 1
    print(f"200x120 逻辑区域裁剪结果：{region.width()}x{region.height()}")
    ok_region = abs(region.width() - 200 * dpr) <= 6 and abs(region.height() - 120 * dpr) <= 6
    if not ok_region:
        print(f"FAIL：区域尺寸异常（期望约 {200 * dpr:.0f}x{120 * dpr:.0f}）")
        return 1

    print("PASS：截屏与 DPR 换算测试通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
