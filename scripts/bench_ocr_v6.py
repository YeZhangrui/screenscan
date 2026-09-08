"""RapidOCR v3.9 (PP-OCRv6) 性能与精度基准，与 v3 基线对比。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.gen_fixture import build_fixture

FULL = Path(__file__).parent.parent / "tests" / "_artifacts" / "bench_full.png"


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


def texts_of(out):
    if out is None:
        return []
    if hasattr(out, "txts"):
        return [str(t) for t in out.txts]
    return [str(x[1] if isinstance(x, (list, tuple)) else x.get("text", "")) for x in (out or [])]


def main() -> int:
    from rapidocr import RapidOCR

    report = {}
    t0 = time.perf_counter()
    try:
        eng = RapidOCR(params={"Global.use_cls": False})
    except Exception as e:
        report["init_error"] = str(e)
        print(json.dumps(report, ensure_ascii=False))
        return 1
    report["init_v6_s"] = round(time.perf_counter() - t0, 2)

    fixture = build_fixture()
    dt, _out = timeit(lambda: eng(str(fixture)), repeat=3)
    report["region_v6_s"] = round(dt, 2)
    report["region_v6_items"] = len(_out or [])
    report["region_v6_texts"] = texts_of(_out)

    dt, _out = timeit(lambda: eng(str(FULL)), repeat=1)
    report["full_v6_s"] = round(dt, 2)
    report["full_v6_items"] = len(_out or [])
    report["full_v6_texts"] = texts_of(_out)

    # 对比 v3 基线文本覆盖率（V3 71 项的文本集合）
    baseline = ["Bambu", "Docker", "DeepSeek", "Harness", "DSH", "Steam", "bilibili",
                "Kazumi", "NewsNow", "CodeArts", "Agent", "Edge", "PDF", "Snipaste",
                "Visual", "Microsoft", "python", "Desktop", "Data", "Format", "Kimi"]
    report["full_v6_hits"] = sum(1 for b in baseline
                                 if any(b in t for t in report["full_v6_texts"]))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
