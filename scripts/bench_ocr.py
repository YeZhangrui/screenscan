"""OCR 性能基准：对比 默认 / 关cls / 降采样 三种配置。

输出：引擎初始化耗时、区域/全屏识别耗时、识别数量（验证准确率不劣化）。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np

from tests.gen_fixture import build_fixture


def timeit(fn, repeat=1):
    best = None
    result = None
    for _ in range(repeat):
        t0 = time.perf_counter()
        out = fn()
        dt = time.perf_counter() - t0
        best = dt if best is None else min(best, dt)
        result = out[0] if isinstance(out, tuple) else out
    return best, result


def make_full(path: Path) -> Path:
    """截取真实全屏并保存（仅基准用）。"""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QGuiApplication
    from src.capture import grab_fullscreen

    path.parent.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    screen = QGuiApplication.primaryScreen()
    pm = grab_fullscreen(screen)
    assert pm is not None and not pm.isNull(), "全屏截图失败"
    assert pm.save(str(path), "PNG"), f"保存失败：{path}"
    return path


def texts_of(out):
    return [str(x[1] if isinstance(x, (list, tuple)) else x.get("text", "")) for x in (out or [])]


def main() -> int:
    fixture = build_fixture()
    full = Path(__file__).parent.parent / "tests" / "_artifacts" / "bench_full.png"
    if not full.exists():
        make_full(full)

    report = {"cpu_cores": __import__("os").cpu_count()}

    # ---------- 基线：默认配置 ----------
    from rapidocr_onnxruntime import RapidOCR

    t0 = time.perf_counter()
    eng0 = RapidOCR()
    report["init_default_s"] = round(time.perf_counter() - t0, 2)

    dt, _out = timeit(lambda: eng0(str(fixture)), repeat=3)
    report["region_default_s"] = round(dt, 2)
    report["region_default_items"] = len(_out or [])

    dt, _out = timeit(lambda: eng0(str(full)), repeat=1)
    report["full_default_s"] = round(dt, 2)
    report["full_default_items"] = len(_out or [])
    report["full_default_texts"] = texts_of(_out)

    # ---------- 方案A：关闭方向分类 ----------
    t0 = time.perf_counter()
    engA = RapidOCR(use_angle_cls=False, det_model_path="")
    report["init_nocls_s"] = round(time.perf_counter() - t0, 2)

    dt, _out = timeit(lambda: engA(str(fixture)), repeat=3)
    report["region_nocls_s"] = round(dt, 2)
    report["region_nocls_items"] = len(_out or [])

    dt, _out = timeit(lambda: engA(str(full)), repeat=1)
    report["full_nocls_s"] = round(dt, 2)
    report["full_nocls_items"] = len(_out or [])
    report["full_nocls_texts"] = texts_of(_out)

    # ---------- 方案B：方案A + 检测降采样（max 1600） ----------
    try:
        t0 = time.perf_counter()
        engB = RapidOCR(
            use_angle_cls=False, det_model_path="",
            det_limit_type="max", det_limit_side_len=1600,
        )
        report["init_B_s"] = round(time.perf_counter() - t0, 2)
        dt, _out = timeit(lambda: engB(str(full)), repeat=1)
        report["full_B_s"] = round(dt, 2)
        report["full_B_items"] = len(_out or [])
        report["full_B_texts"] = texts_of(_out)
    except Exception as e:
        report["full_B_error"] = str(e)

    # ---------- 方案C：方案A + cv2 预降采样（max 1600） ----------
    img = cv2.imdecode(np.fromfile(str(full), dtype=np.uint8), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    scale = min(1.0, 1600 / max(h, w))
    img_small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    cv2.imencode(".png", img_small)[1].tofile(str(full.with_name("bench_full_small.png")))

    def runC():
        return engA(str(full.with_name("bench_full_small.png")))

    dt, _out = timeit(runC, repeat=1)
    report["full_C_s"] = round(dt, 2)
    report["full_C_items"] = len(_out or [])
    report["full_C_texts"] = texts_of(_out)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

