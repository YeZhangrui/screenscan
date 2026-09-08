"""屏幕扫描助手 - 配置与数据目录管理。"""
from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "ScreenScan"
APP_TITLE = "屏幕扫描助手"
APP_VERSION = "1.0.0"

DEFAULTS = {
    "hotkey_capture": "alt+s",        # 框选截图识别热键 (pynput 格式)
    "hotkey_fullscreen": "alt+shift+s",  # 全屏扫描热键
    "pin_result": True,               # 结果窗默认置顶
    "autostart": False,               # 开机自启
    "history_limit": 50,              # 历史记录条数上限
}


def data_dir() -> Path:
    """应用数据目录：%LOCALAPPDATA%\\ScreenScan"""
    base = os.environ.get("LOCALAPPDATA")
    d = Path(base) / APP_NAME if base else Path.home() / f".{APP_NAME}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def tmp_dir() -> Path:
    d = data_dir() / "tmp"
    d.mkdir(parents=True, exist_ok=True)
    return d


class Config:
    """JSON 设置存储；读取失败时回退默认值，保存失败不中断程序。"""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else data_dir() / "config.json"
        self.data: dict = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            if self.path.exists():
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                for k in DEFAULTS:
                    if k in loaded:
                        self.data[k] = loaded[k]
        except Exception:
            pass  # 配置损坏时使用默认值

    def save(self) -> None:
        try:
            self.path.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def get(self, key: str, default=None):
        return self.data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value) -> None:
        self.data[key] = value
        self.save()
