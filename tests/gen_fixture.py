"""生成 OCR 测试用图：白底 + 中英文文字。"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "_artifacts"
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def build_fixture() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (760, 300), "white")
    d = ImageDraw.Draw(img)
    f1 = _font(34)
    d.text((20, 20), "屏幕扫描助手 ScreenScan", fill="black", font=f1)
    d.text((20, 90), "功能测试：文字识别 12345", fill="black", font=f1)
    d.text((20, 160), "Hello World! 本地离线识别", fill="black", font=f1)
    d.text((20, 230), "Alt+S 框选截图识别", fill="black", font=f1)
    path = OUT / "fixture.png"
    img.save(path)
    return path


if __name__ == "__main__":
    print(build_fixture())
