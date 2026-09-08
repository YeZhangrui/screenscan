"""热键解析测试。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.hotkeys import is_valid_hotkey, pretty_hotkey, to_pynput

CASES_VALID = {
    "alt+s": "<alt>+s",
    "ctrl+alt+s": "<alt>+<ctrl>+s",
    "alt+shift+s": "<alt>+<shift>+s",
    "f9": "f9",
    "ctrl+s": "<ctrl>+s",
    "Alt+S": "<alt>+s",
    "alt + shift + f10": "<alt>+<shift>+f10",
    "alt+s+shift": "<alt>+<shift>+s",
}
CASES_INVALID = ["", "alt", "ctrl+alt", "x+y", "f25", "ctrl+alt+s2"]


def main() -> int:
    for src, want in CASES_VALID.items():
        assert is_valid_hotkey(src), f"应当合法：{src}"
        got = to_pynput(src)
        assert got == want, f"{src} -> {got} != {want}"
    for src in CASES_INVALID:
        assert not is_valid_hotkey(src), f"应当非法：{src}"
    assert pretty_hotkey("alt+shift+s") == "Alt + Shift + S"
    assert pretty_hotkey("f9") == "F9"
    print("PASS：热键解析测试通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
