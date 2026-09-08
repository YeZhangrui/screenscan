"""生成应用图标 assets/icon.ico（淡蓝圆角底 + 白色放大镜）。"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 256


def build() -> Path:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, 248, 248], radius=56, fill=(47, 128, 214, 255))
    # 放大镜圆环
    d.ellipse([66, 66, 162, 162], outline=(255, 255, 255, 255), width=24)
    # 手柄
    d.line([148, 148, 196, 196], fill=(255, 255, 255, 255), width=26)
    out = Path(__file__).parent.parent / "assets" / "icon.ico"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(
        out,
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return out


if __name__ == "__main__":
    print(build())
