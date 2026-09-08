"""OCR 引擎冒烟测试：对合成中文图片识别。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ocr_engine import OcrEngine
from tests.gen_fixture import build_fixture

EXPECTED = ["屏幕扫描助手", "功能测试", "12345", "Hello", "World", "框选截图识别"]


def main() -> int:
    fixture = build_fixture()
    engine = OcrEngine()
    print("加载 OCR 引擎…")
    items = engine.recognize_sync(str(fixture))
    texts = [it["text"] for it in items]
    print(f"识别到 {len(texts)} 段：")
    for t in texts:
        print("  -", t)
    joined = " ".join(texts)
    failed = [e for e in EXPECTED if e not in joined]
    if failed:
        print(f"FAIL：以下关键内容未识别到：{failed}")
        return 1
    print("PASS：OCR 核心内容全部命中")
    return 0


if __name__ == "__main__":
    sys.exit(main())
