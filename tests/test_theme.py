"""主题系统测试：浅色 / 深色 / 跟随系统 三模式。"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from src.config import Config
from src.history import HistoryStore
from src.main_window import MainWindow
from src.result_window import ResultWindow
from src.settings_window import SettingsDialog
from src.theme import (
    DARK,
    LIGHT,
    MODE_DARK,
    MODE_LIGHT,
    MODE_SYSTEM,
    apply_theme,
    qss,
    resolve_mode,
)


def main() -> int:
    app = QApplication(sys.argv)
    tmp = Path(tempfile.mkdtemp(prefix="screenscan_theme_"))

    # 1) 两套调色板样式表都可用且互不相同
    light_qss, dark_qss = qss(LIGHT), qss(DARK)
    assert LIGHT.bg in light_qss and DARK.bg in dark_qss
    assert light_qss != dark_qss

    # 2) 模式解析
    assert resolve_mode(MODE_LIGHT) == MODE_LIGHT
    assert resolve_mode(MODE_DARK) == MODE_DARK
    assert resolve_mode(MODE_SYSTEM) in (MODE_LIGHT, MODE_DARK)
    assert resolve_mode("") in (MODE_LIGHT, MODE_DARK)

    # 3) 应用主题：样式表 + 调色板 + 属性
    p = apply_theme(app, MODE_DARK)
    assert p.name == MODE_DARK
    assert app.property("theme_effective") == MODE_DARK
    assert app.palette().color(QPalette.Window).name().lower() == DARK.bg.lower()

    p = apply_theme(app, MODE_LIGHT)
    assert app.property("theme_effective") == MODE_LIGHT
    assert app.palette().color(QPalette.Window).name().lower() == LIGHT.bg.lower()

    # 4) 深色下实例化窗口不报错
    apply_theme(app, MODE_DARK)
    config = Config(path=tmp / "config.json")
    history = HistoryStore(root=tmp / "history", limit=5)
    main_win = MainWindow(config, history)
    result_win = ResultWindow(config)
    from PySide6.QtGui import QPixmap

    pm = QPixmap(300, 120)
    pm.fill("black")
    result_win.show_result(pm, [{"box": [[0, 0], [100, 0], [100, 20], [0, 20]],
                                "text": "深色主题测试", "score": 0.9}], "测试")
    assert result_win.listw.count() == 1

    # 5) 配置默认值 + 设置窗口主题选项
    assert config.get("theme") == MODE_SYSTEM
    dlg = SettingsDialog(config, lambda c, f: None, main_win)
    assert set(dlg.theme_buttons.keys()) == {MODE_SYSTEM, MODE_LIGHT, MODE_DARK}
    assert dlg.selected_theme() == MODE_SYSTEM
    dlg.theme_buttons[MODE_DARK].setChecked(True)
    assert dlg.selected_theme() == MODE_DARK
    config.set("theme", dlg.selected_theme())
    assert Config(path=tmp / "config.json").get("theme") == MODE_DARK
    dlg.close()

    print("PASS：主题系统测试通过（浅色/深色/跟随系统）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
