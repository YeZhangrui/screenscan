"""控制器识别链路回归测试。

覆盖曾经导致「识别永远卡在正在识别」的 bug：
_process 中的托盘通知使用了实例枚举 self.tray.Information（PySide6 会抛 AttributeError），
异常发生在发起识别之前，导致任务永不启动。本测试确保：
1) _process 不抛异常且确实发起了识别任务；
2) 托盘通知失败不影响主流程；
3) 识别完成回调能正常更新状态与结果窗。
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtCore import QObject
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from src.app_controller import AppController, _notify
from src.config import Config
from src.history import HistoryStore
from src.main_window import MainWindow
from src.result_window import ResultWindow
from src.theme import apply_theme
from src.tray import Tray
from src.widgets import make_app_icon


class StubOcr(QObject):
    """记录调用的假引擎。"""

    def __init__(self):
        super().__init__()
        self.calls = []

    def recognize_async(self, job: str, image_path: str) -> None:
        self.calls.append((job, image_path))

    def preload_async(self) -> None:
        pass


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)
    tmp = Path(tempfile.mkdtemp(prefix="screenscan_flow_"))

    config = Config(path=tmp / "config.json")
    history = HistoryStore(root=tmp / "history", limit=5)
    main_win = MainWindow(config, history)
    result_win = ResultWindow(config)
    tray = Tray(make_app_icon(), "alt+s")
    stub = StubOcr()

    controller = AppController(config, stub, main_win, result_win, tray, history)

    pm = QPixmap(200, 80)
    pm.fill("white")

    # 1) 关键回归点：_process 必须不抛异常且发起识别
    controller._process(pm, "框选识别")
    assert len(stub.calls) == 1, "未发起识别任务"
    job, image_path = stub.calls[0]
    assert Path(image_path).exists(), f"待识别图片不存在：{image_path}"

    # 2) 托盘通知不得影响主流程
    _notify(tray, "测试通知")
    _notify(tray, "测试警告", warning=True)

    # 3) 识别完成回调：状态更新 + 结果窗内容
    items = [{"box": [[0, 0], [100, 0], [100, 30], [0, 30]], "text": "回归测试文字", "score": 0.99}]
    controller.on_ocr_done(job, items)
    assert "识别完成" in main_win.label_status.text(), main_win.label_status.text()
    assert result_win.listw.count() == 1
    assert "回归测试文字" in result_win.full_text()

    # 4) 失败回调：状态与窗口恢复
    controller._process(pm, "全屏扫描")
    job2 = stub.calls[1][0]
    controller.on_ocr_failed(job2, "模拟失败")
    assert main_win.label_status.text() == "识别失败"

    print("PASS：控制器识别链路回归测试通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
