"""UI 冒烟测试：offscreen 平台实例化所有窗口，验证无异常。"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication

from src.config import Config
from src.ocr_engine import OcrEngine
from src.history import HistoryStore
from src.hotkeys import HotkeySignals
from src.main_window import MainWindow
from src.result_window import ResultWindow
from src.widgets import make_app_icon


def main() -> int:
    app = QApplication(sys.argv)
    from src.theme import apply_theme
    apply_theme(app)

    # 用独立临时目录，避免污染真实数据
    tmp_root = Path(tempfile.mkdtemp(prefix="screenscan_test_"))
    config = Config(path=tmp_root / "config.json")
    history = HistoryStore(root=tmp_root / "history", limit=5)
    ocr = OcrEngine()
    signals = HotkeySignals()

    main_win = MainWindow(config, history)
    result_win = ResultWindow(config)
    icon = make_app_icon()
    assert not icon.isNull(), "图标生成失败"

    # 模拟一次结果展示
    from PySide6.QtGui import QPixmap
    pm = QPixmap(640, 240)
    pm.fill("white")
    items = [
        {"box": [[10, 10], [200, 10], [200, 50], [10, 50]], "text": "测试文字一", "score": 0.95},
        {"box": [[10, 60], [300, 60], [300, 100], [10, 100]], "text": "测试文字二", "score": 0.9},
    ]
    result_win.show_result(pm, items, "测试")
    assert result_win.listw.count() == 2
    result_win.copy_all_text()
    assert "测试文字" in result_win.full_text()

    # 历史记录读写
    history.add("框选识别", "历史文本测试", pm)
    assert len(history.list()) == 1
    rid = history.list()[0]["id"]
    assert history.resolve(history.list()[0]["image"]).exists()
    history.delete(rid)
    assert len(history.list()) == 0

    print("PASS：UI 冒烟测试通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
