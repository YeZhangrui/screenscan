"""新交互测试：屏幕浮层就地选择复制 + 结果窗多选复制。"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.config import Config
from src.history import HistoryStore
from src.onscreen_result import OnScreenResult
from src.result_window import ResultWindow
from src.theme import apply_theme

ITEMS = [
    {"box": [[10, 10], [150, 10], [150, 40], [10, 40]], "text": "第一段文字", "score": 0.99},
    {"box": [[10, 60], [150, 60], [150, 90], [10, 90]], "text": "第二段文字", "score": 0.98},
    {"box": [[10, 110], [150, 110], [150, 140], [10, 140]], "text": "第三段文字", "score": 0.97},
]


def make_pixmap(w=400, h=200) -> QPixmap:
    pm = QPixmap(w, h)
    pm.fill("white")
    return pm


def test_onscreen(app: QApplication) -> None:
    screen = QGuiApplication.primaryScreen()
    panel = OnScreenResult(make_pixmap(), ITEMS, screen, QRect(50, 50, 400, 200), dpr=1.0)
    panel.show()
    app.processEvents()

    # 0) 操作条必须是独立窗口且位于面板外面（不被面板遮挡）
    assert panel.toolbar.isVisible(), "操作条未显示"
    assert not panel.toolbar.geometry().intersects(panel.geometry()), (
        f"操作条压在面板上：{panel.toolbar.geometry()} vs {panel.geometry()}"
    )

    # 1) 点击第 1 段 → 选中 1 段 → 复制
    QTest.mouseClick(panel, Qt.LeftButton, Qt.NoModifier, QPoint(60, 25))
    app.processEvents()
    assert panel._selected == {0}, panel._selected
    panel.copy_selected()
    assert QGuiApplication.clipboard().text() == "第一段文字"

    # 2) Ctrl+点击第 2 段 → 多选 2 段
    QTest.mouseClick(panel, Qt.LeftButton, Qt.ControlModifier, QPoint(60, 75))
    app.processEvents()
    assert panel._selected == {0, 1}, panel._selected
    panel.copy_selected()
    assert QGuiApplication.clipboard().text() == "第一段文字\n第二段文字"

    # 3) Ctrl+A 全选 → 复制全部
    QTest.keyClick(panel, Qt.Key_A, Qt.ControlModifier)
    app.processEvents()
    assert len(panel._selected) == 3
    panel.copy_selected()
    assert QGuiApplication.clipboard().text().count("\n") == 2

    # 4) 拖拽框选：清空后从空白拖过前两段
    panel._selected.clear()
    QTest.mousePress(panel, Qt.LeftButton, Qt.NoModifier, QPoint(200, 5))
    QTest.mouseMove(panel, QPoint(5, 100))
    QTest.mouseRelease(panel, Qt.LeftButton, Qt.NoModifier, QPoint(5, 100))
    app.processEvents()
    assert panel._selected == {0, 1}, panel._selected

    # 5) Esc 关闭（操作条一并关闭）
    closed = {"v": False}
    panel.closed.connect(lambda: closed.update(v=True))
    QTest.keyClick(panel, Qt.Key_Escape)
    app.processEvents()
    assert closed["v"], "Esc 未关闭浮层"
    assert not panel.toolbar.isVisible(), "操作条未随面板关闭"
    print("PASS：屏幕浮层就地选择复制")


def test_tiny_region(app: QApplication) -> None:
    """极小框选区域：面板自动放大到可用尺寸，操作条仍在外面且能关闭。"""
    from src.onscreen_result import MIN_PANEL_H, MIN_PANEL_W

    screen = QGuiApplication.primaryScreen()
    panel = OnScreenResult(make_pixmap(120, 40), ITEMS, screen, QRect(100, 100, 120, 40), dpr=1.0)
    panel.show()
    app.processEvents()
    assert panel.width() >= MIN_PANEL_W, f"面板过小：{panel.width()}"
    assert panel.height() >= MIN_PANEL_H, f"面板过小：{panel.height()}"
    assert not panel.toolbar.geometry().intersects(panel.geometry()), "小区域时操作条压住面板"

    closed = {"v": False}
    panel.closed.connect(lambda: closed.update(v=True))
    QTest.mouseClick(panel.toolbar.btn_close, Qt.LeftButton)
    app.processEvents()
    assert closed["v"], "点「关闭」未关闭浮层"
    print("PASS：极小区域可用性（放大 + 操作条在外 + 可关闭）")


def test_result_multiselect(app: QApplication, tmp: Path) -> None:
    config = Config(path=tmp / "config.json")
    win = ResultWindow(config)
    win.show_result(make_pixmap(), ITEMS, "测试")
    app.processEvents()
    assert win.listw.count() == 3

    # 勾选第 1、3 段 → 复制选中
    win.listw.item(0).setCheckState(Qt.Checked)
    win.listw.item(2).setCheckState(Qt.Checked)
    app.processEvents()
    assert win.selected_texts() == ["第一段文字", "第三段文字"]
    win.copy_selected()
    assert QGuiApplication.clipboard().text() == "第一段文字\n第三段文字"

    # 全选 / 取消全选
    win.toggle_select_all(True)
    assert len(win.selected_texts()) == 3
    win.toggle_select_all(False)
    assert win.selected_texts() == []

    # 复制全部仍可用
    win.copy_all_text()
    assert QGuiApplication.clipboard().text().count("\n") == 2
    print("PASS：结果窗多选复制")


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)
    tmp = Path(tempfile.mkdtemp(prefix="screenscan_sel_"))
    test_onscreen(app)
    test_tiny_region(app)
    test_result_multiselect(app, tmp)
    print("PASS：新交互测试全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
