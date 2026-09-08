"""生成界面截图（offscreen 渲染）供使用说明使用。"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from src.config import Config
from src.history import HistoryStore
from src.main_window import MainWindow
from src.result_window import ResultWindow
from src.theme import apply_theme

OUT = Path(__file__).parent.parent / "docs" / "screenshots"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    apply_theme(app)

    tmp = Path(tempfile.mkdtemp(prefix="screenscan_shot_"))
    config = Config(path=tmp / "config.json")
    history = HistoryStore(root=tmp / "history")

    # —— 主窗口 ——
    main_win = MainWindow(config, history)
    main_win.resize(780, 580)
    main_win.show()
    app.processEvents()
    main_win.grab().save(str(OUT / "main.png"), "PNG")

    # —— 结果窗口 ——
    pm = QPixmap(720, 300)
    pm.fill("white")
    items = [
        {"box": [[16, 14], [400, 14], [400, 56], [16, 56]],
         "text": "屏幕扫描助手 ScreenScan — 本地离线识别", "score": 0.97},
        {"box": [[16, 70], [310, 70], [310, 112], [16, 112]],
         "text": "功能测试：文字识别 12345", "score": 0.99},
        {"box": [[16, 126], [330, 126], [330, 168], [16, 168]],
         "text": "Hello World! 识别框用蓝色标注", "score": 0.95},
        {"box": [[16, 182], [260, 182], [260, 224], [16, 224]],
         "text": "Alt+S 框选截图识别", "score": 0.96},
    ]
    result_win = ResultWindow(config)
    result_win.resize(900, 580)
    result_win.show_result(pm, items, "框选识别")
    app.processEvents()
    result_win.grab().save(str(OUT / "result.png"), "PNG")

    print(f"OK: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
