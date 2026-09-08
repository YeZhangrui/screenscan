"""真实尺寸区域基准：从全屏截图中裁剪两个典型区域，v3 vs v6 对比。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np

FULL = Path(__file__).parent.parent / "tests" / "_artifacts" / "bench_full.png"


def load():
    return cv2.imdecode(np.fromfile(str(FULL), dtype=np.uint8), cv2.IMREAD_COLOR)


def timeit(fn, repeat=3):
    best = None
    result = None
    for _ in range(repeat):
        t0 = time.perf_counter()
        out = fn()
        dt = time.perf_counter() - t0
        best = dt if best is None else min(best, dt)
        result = out
    return best, result


def texts_of(out):
    if out is None:
        return []
    if hasattr(out, "txts"):
        return [str(t) for t in out.txts]
    return [str(x[1]) for x in (out or [])]


def main() -> int:
    img = load()
    h, w = img.shape[:2]
    regions = {
        "区域A_1280x400": img[0:400, 0:1280],
        "区域B_800x300": img[300:600, 600:1400],
    }
    for name, reg in regions.items():
        reg_path = FULL.parent / f"bench_{name.split('_')[0]}.png"
        cv2.imencode(".png", reg)[1].tofile(str(reg_path))
        paths = [str(reg_path)]

        from rapidocr_onnxruntime import RapidOCR as V3
        from rapidocr import RapidOCR as V6
        e3 = V3(use_angle_cls=False, det_model_path="")
        e6 = V6(params={"Global.use_cls": False})

        dt3, o3 = timeit(lambda: e3(paths[0]))
        dt6, o6 = timeit(lambda: e6(paths[0]))
        print(json.dumps({
            name: {
                "v3_s": round(dt3, 2), "v3_items": len(o3 or []),
                "v6_s": round(dt6, 2), "v6_items": len(o6.txts) if hasattr(o6, "txts") else len(o6 or []),
                "v3_sample": texts_of(o3)[:6],
                "v6_sample": texts_of(o6)[:6],
            }
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
