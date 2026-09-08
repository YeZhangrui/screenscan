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

    # 0.1) 圆角透明：面板与操作条四角都应为透明（不再有白色方角）
    for name, widget in (("面板", panel), ("操作条", panel.toolbar)):
        img = widget.grab().toImage()
        corners = [
            img.pixelColor(0, 0), img.pixelColor(img.width() - 1, 0),
            img.pixelColor(0, img.height() - 1),
            img.pixelColor(img.width() - 1, img.height() - 1),
        ]
        assert all(c.alpha() == 0 for c in corners), (
            f"{name}四角不透明：{[ (c.red(), c.green(), c.blue(), c.alpha()) for c in corners ]}"
        )

    # 1) 单击第 1 段 → 选中 1 段 → 复制
    QTest.mouseClick(panel, Qt.LeftButton, Qt.NoModifier, QPoint(60, 25))
    app.processEvents()
    assert panel._selected == {0}, panel._selected
    panel.copy_selected()
    assert QGuiApplication.clipboard().text() == "第一段文字"

    # 1.1) 不按 Ctrl 直接点第 2 段 → 累加多选（本次需求重点）
    QTest.mouseClick(panel, Qt.LeftButton, Qt.NoModifier, QPoint(60, 75))
    app.processEvents()
    assert panel._selected == {0, 1}, panel._selected
    panel.copy_selected()
    assert QGuiApplication.clipboard().text() == "第一段文字\n第二段文字"

    # 1.2) 再点第 2 段一次 → 取消该段
    QTest.mouseClick(panel, Qt.LeftButton, Qt.NoModifier, QPoint(60, 75))
    app.processEvents()
    assert panel._selected == {0}, panel._selected

    # 1.3) Shift + 点击第 3 段 → 从上次点击（第 2 段）连选到第 3 段
    QTest.mouseClick(panel, Qt.LeftButton, Qt.ShiftModifier, QPoint(60, 125))
    app.processEvents()
    assert panel._selected == {1, 2}, panel._selected

    # 1.4) 点空白处 → 清空选择
    QTest.mouseClick(panel, Qt.LeftButton, Qt.NoModifier, QPoint(320, 180))
    app.processEvents()
    assert panel._selected == set(), panel._selected

    # 1.5) 单击第 1 段后 Shift + 点击第 3 段 → 连选 1~3 段
    QTest.mouseClick(panel, Qt.LeftButton, Qt.NoModifier, QPoint(60, 25))
    QTest.mouseClick(panel, Qt.LeftButton, Qt.ShiftModifier, QPoint(60, 125))
    app.processEvents()
    assert panel._selected == {0, 1, 2}, panel._selected

    # 2) Ctrl+点击方式保留可用（先点空白清空）
    QTest.mouseClick(panel, Qt.LeftButton, Qt.NoModifier, QPoint(320, 180))
    app.processEvents()
    assert panel._selected == set()
    QTest.mouseClick(panel, Qt.LeftButton, Qt.NoModifier, QPoint(60, 25))
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

    # 4) 拖拽框选：从面板内部（避开边缘缩放区）拖过前两段
    panel._selected.clear()
    QTest.mousePress(panel, Qt.LeftButton, Qt.NoModifier, QPoint(300, 30))
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
    pm = make_pixmap(120, 40)
    panel = OnScreenResult(pm, ITEMS, screen, QRect(100, 100, 120, 40), dpr=1.0)
    panel.show()
    app.processEvents()
    assert panel.width() >= MIN_PANEL_W, f"面板过小：{panel.width()}"
    assert panel.height() >= MIN_PANEL_H, f"面板过小：{panel.height()}"
    assert not panel.toolbar.geometry().intersects(panel.geometry()), "小区域时操作条压住面板"

    # 关键：放大后必须保持原始宽高比（否则文字与识别框会错位）
    ratio_panel = panel.width() / panel.height()
    ratio_pixmap = pm.width() / pm.height()
    assert abs(ratio_panel - ratio_pixmap) < 0.05, (
        f"宽高比被改变：面板 {ratio_panel:.2f} vs 原图 {ratio_pixmap:.2f}"
    )

    # 关键：坐标映射必须与绘制区域一致（框与文字对齐）
    dr = panel._draw_rect
    assert panel._to_panel((0, 0)) == dr.topLeft(), "左上角映射不一致"
    br = panel._to_panel((pm.width(), pm.height()))
    assert abs(br.x() - (dr.x() + dr.width())) <= 1, "右下角 x 映射不一致"
    assert abs(br.y() - (dr.y() + dr.height())) <= 1, "右下角 y 映射不一致"

    closed = {"v": False}
    panel.closed.connect(lambda: closed.update(v=True))
    QTest.mouseClick(panel.toolbar.btn_close, Qt.LeftButton)
    app.processEvents()
    assert closed["v"], "点「关闭」未关闭浮层"
    print("PASS：极小区域可用性（等比放大 + 操作条在外 + 坐标对齐 + 可关闭）")


def test_resize(app: QApplication) -> None:
    """拖拽面板边缘可缩放：等比、有下限、操作条自动跟随且不重叠。"""
    from src.onscreen_result import MIN_RESIZE_H, MIN_RESIZE_W

    screen = QGuiApplication.primaryScreen()
    pm = make_pixmap(600, 200)
    panel = OnScreenResult(pm, ITEMS, screen, QRect(120, 120, 600, 200), dpr=1.0)
    panel.show()
    app.processEvents()
    w0, h0 = panel.width(), panel.height()
    aspect = pm.width() / pm.height()

    # 1) 拖右边缘放大
    QTest.mousePress(panel, Qt.LeftButton, Qt.NoModifier, QPoint(w0 - 2, h0 // 2))
    QTest.mouseMove(panel, QPoint(w0 - 2 + 150, h0 // 2))
    QTest.mouseRelease(panel, Qt.LeftButton, Qt.NoModifier, QPoint(w0 - 2 + 150, h0 // 2))
    app.processEvents()
    assert panel.width() > w0 + 100, f"右边缘拖拽未放大：{panel.width()} (原 {w0})"
    assert abs(panel.width() / panel.height() - aspect) < 0.05, "缩放后宽高比被破坏"
    assert not panel.toolbar.geometry().intersects(panel.geometry()), "缩放后操作条压住面板"

    # 2) 拖右下角缩小到极限 → 不低于下限
    w1, h1 = panel.width(), panel.height()
    QTest.mousePress(panel, Qt.LeftButton, Qt.NoModifier, QPoint(w1 - 2, h1 - 2))
    QTest.mouseMove(panel, QPoint(panel.x() + 5, panel.y() + 5))
    QTest.mouseRelease(panel, Qt.LeftButton, Qt.NoModifier, QPoint(panel.x() + 5, panel.y() + 5))
    app.processEvents()
    assert panel.width() >= MIN_RESIZE_W, f"缩得比下限还小：{panel.width()}"
    assert panel.height() >= MIN_RESIZE_H - 1, f"缩得比下限还小：{panel.height()}"

    # 3) 缩放后坐标映射仍然一致（框与文字对齐）
    dr = panel._draw_rect
    assert panel._to_panel((0, 0)) == dr.topLeft()
    panel.close()
    print("PASS：浮层拖拽缩放（等比 + 下限 + 操作条跟随 + 映射一致）")


def test_processing_then_result(app: QApplication) -> None:
    """框选后先显示截图占位面板（正在识别），识别完成后原地升级为可交互。"""
    screen = QGuiApplication.primaryScreen()
    panel = OnScreenResult(make_pixmap(), [], screen, QRect(60, 60, 500, 200),
                           dpr=1.0, processing=True)
    panel.show()
    app.processEvents()
    assert panel._processing, "未进入处理中状态"
    assert "正在识别" in panel.toolbar.label_hint.text(), panel.toolbar.label_hint.text()
    assert not panel.toolbar.btn_copy_sel.isEnabled(), "处理中「复制选中」应为禁用"
    assert not panel.toolbar.btn_copy_all.isEnabled(), "处理中「复制全部」应为禁用"
    assert panel.toolbar.btn_close.isEnabled(), "处理中「关闭」应可用"

    # 原地升级
    panel.apply_result(ITEMS)
    app.processEvents()
    assert not panel._processing and not panel._error
    assert len(panel.items()) == 3
    assert panel.toolbar.btn_copy_sel.isEnabled()
    assert "框选" in panel.toolbar.label_hint.text()

    # 失败提示
    panel.apply_error("识别失败，请重试")
    app.processEvents()
    assert "识别失败" in panel.toolbar.label_hint.text()
    assert not panel.toolbar.btn_copy_sel.isEnabled()
    panel.close()
    print("PASS：占位面板 → 原地升级 / 失败提示")


def test_extract_on_onscreen(app: QApplication) -> None:
    """快捷键浮层里的「提取图片」：拖拽裁剪 → 复制到剪贴板 → 可保存。"""
    screen = QGuiApplication.primaryScreen()
    pm = make_pixmap(600, 200)
    panel = OnScreenResult(pm, ITEMS, screen, QRect(100, 100, 600, 200), dpr=1.0)
    panel.show()
    app.processEvents()
    assert not panel.toolbar.btn_save_crop.isVisible(), "初始不应显示保存提取图按钮"

    # 开启提取模式：清空文字选择，进入十字光标
    panel.toolbar.btn_extract.setChecked(True)
    app.processEvents()
    assert panel._extract_mode
    assert panel._selected == set()

    # 拖拽裁剪 140×90（scale=1）
    QTest.mousePress(panel, Qt.LeftButton, Qt.NoModifier, QPoint(60, 30))
    QTest.mouseMove(panel, QPoint(200, 120))
    QTest.mouseRelease(panel, Qt.LeftButton, Qt.NoModifier, QPoint(200, 120))
    app.processEvents()
    assert panel._crop is not None, "未生成提取图片"
    assert panel.toolbar.btn_save_crop.isVisible(), "「保存提取图」按钮未出现"
    img = QGuiApplication.clipboard().image()
    assert not img.isNull(), "提取的图片未进入剪贴板"
    assert abs(img.width() - 140) <= 2 and abs(img.height() - 90) <= 2, (
        f"提取尺寸不符：{img.width()}×{img.height()}（期望约 140×90）"
    )
    assert not panel._extract_mode, "提取完成后应自动退出提取模式"

    # 提取模式下 Esc 先退出模式（不关闭面板）
    panel.toolbar.btn_extract.setChecked(True)
    app.processEvents()
    QTest.keyClick(panel, Qt.Key_Escape)
    app.processEvents()
    assert not panel._extract_mode and panel.isVisible(), "Esc 应只退出提取模式"

    # 退出提取模式后文字选择仍正常
    QTest.mouseClick(panel, Qt.LeftButton, Qt.NoModifier, QPoint(60, 25))
    app.processEvents()
    assert panel._selected == {0}
    panel.close()
    print("PASS：浮层「提取图片」拖拽裁剪 + 复制 + 可保存")


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

    # 回归：隐藏状态下同步置顶开关（如切换主题/保存设置）不得把窗口弹出来
    win.hide()
    app.processEvents()
    assert not win.isVisible()
    win.ensure_pin()
    app.processEvents()
    assert not win.isVisible(), "ensure_pin() 不应让隐藏的结果窗弹出"

    # 可见时切换置顶应保持可见
    win.show()
    app.processEvents()
    win.btn_pin.setChecked(not win.btn_pin.isChecked())
    app.processEvents()
    assert win.isVisible(), "可见时切换置顶不应导致窗口消失"
    print("PASS：结果窗多选复制")


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)
    tmp = Path(tempfile.mkdtemp(prefix="screenscan_sel_"))
    test_onscreen(app)
    test_tiny_region(app)
    test_resize(app)
    test_processing_then_result(app)
    test_extract_on_onscreen(app)
    test_result_multiselect(app, tmp)
    print("PASS：新交互测试全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
