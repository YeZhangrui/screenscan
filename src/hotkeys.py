"""全局热键管理（pynput），支持动态改键。

内置格式（存储、设置界面、pynput 通用）：
    alt+s / ctrl+alt+s / alt+shift+s / f9 / ctrl+s / alt+f10 …
转换：普通写法 -> pynput 的 '<alt>+<shift>+s' 形式。
"""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

MODIFIERS = {"alt", "ctrl", "shift", "win", "cmd", "meta"}
NAMED_KEYS = {
    "space", "tab", "enter", "return", "esc", "escape", "backspace", "delete",
    "insert", "home", "end", "left", "right", "up", "down",
    "page_up", "page_down",
}
FKEYS = {f"f{i}" for i in range(1, 21)}


class HotkeySignals(QObject):
    capture_triggered = Signal()
    fullscreen_triggered = Signal()


def _tokens(key_str: str) -> list[str]:
    """把用户写法拆成小写 token 列表。"""
    parts = [p.strip().lower() for p in key_str.replace(",", "+").split("+")]
    parts = [p for p in parts if p]
    # 兼容 '<alt>' 写法
    parts = [p.strip("<>") for p in parts]
    return parts


def is_valid_hotkey(key_str: str) -> bool:
    toks = _tokens(key_str)
    if not toks:
        return False
    modifiers = [t for t in toks if t in MODIFIERS]
    keys = [t for t in toks if t not in MODIFIERS]
    if len(keys) != 1:
        return False
    k = keys[0]
    if len(k) == 1 and k.isalnum():
        return True
    if k in NAMED_KEYS:
        return True
    if k in FKEYS:
        return True
    return False


def to_pynput(key_str: str) -> str:
    """转成 pynput GlobalHotKeys 格式：<alt>+<shift>+s / <alt>+s / f9。"""
    if not is_valid_hotkey(key_str):
        raise ValueError(f"无效的快捷键：{key_str}")
    parts = _tokens(key_str)
    modifiers = ["alt", "ctrl", "shift", "win", "cmd", "meta"]
    mods = sorted([t for t in parts if t in modifiers], key=modifiers.index)
    key = [t for t in parts if t not in modifiers][0]
    out = []
    for m in mods:
        name = "cmd" if m in ("win", "meta") else m
        out.append(f"<{name}>")
    out.append(key if (len(key) != 1 or key.isalpha()) else key)
    return "+".join(out)


def pretty_hotkey(key_str: str) -> str:
    """显示用：'alt+shift+s' -> 'Alt + Shift + S'，'f9' -> 'F9'。"""
    parts = _tokens(key_str)
    if not parts:
        return key_str
    name_map = {"esc": "Esc", "enter": "Enter", "return": "Enter", "page_up": "Page Up",
                "page_down": "Page Down", "space": "Space", "tab": "Tab"}
    out = []
    for p in parts:
        if p in ("alt", "ctrl", "shift", "win", "cmd", "meta"):
            out.append(p.capitalize())
        elif len(p) == 1:
            out.append(p.upper())
        elif p in FKEYS:
            out.append(p.upper())
        else:
            out.append(name_map.get(p, p.capitalize()))
    return " + ".join(out)


class HotkeyManager:
    """应用两份热键映射；失败时返回错误信息。"""

    def __init__(self, signals: HotkeySignals):
        self.signals = signals
        self._listener = None
        self.current = (None, None)

    def apply(self, capture: str, fullscreen: str) -> str | None:
        """挂载热键；成功返回 None，失败返回错误文本。"""
        try:
            from pynput import keyboard

            mapping = {
                to_pynput(capture): self.signals.capture_triggered.emit,
                to_pynput(fullscreen): self.signals.fullscreen_triggered.emit,
            }
            listener = keyboard.GlobalHotKeys(mapping)
        except Exception as e:
            return f"快捷键设置失败：{e}"
        self.stop()
        listener.daemon = True
        listener.start()
        self._listener = listener
        self.current = (capture, fullscreen)
        return None

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
