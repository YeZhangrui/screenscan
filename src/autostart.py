"""开机自启（HKCU Run 键，无需管理员权限）。"""
from __future__ import annotations

import os
import sys

import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "ScreenScan"


def _command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = os.path.abspath(sys.executable)
    pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    runner = pythonw if os.path.exists(pythonw) else exe
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    return f'"{runner}" "{script}"'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, VALUE_NAME)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    """返回是否写入成功。"""
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as k:
            if enabled:
                winreg.SetValueEx(k, VALUE_NAME, 0, winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(k, VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
