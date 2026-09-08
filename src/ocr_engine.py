"""离线 OCR 引擎封装（RapidOCR / onnxruntime）。"""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal


class OcrSignals(QObject):
    """跨线程结果信号（worker 线程 emit，主线程收）。"""
    finished = Signal(str, object)   # job_id, items(list[dict])
    failed = Signal(str, str)        # job_id, message
    state_changed = Signal(bool, str)  # loading, msg


class OcrEngine(QObject):
    """RapidOCR 封装：懒加载 + 后台预加载 + 异步识别。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._engine = None
        self._api = "unknown"
        self._lock = threading.Lock()
        self._load_lock = threading.Lock()
        self._load_error: str | None = None
        self.signals = OcrSignals()

    # ---------- 加载 ----------
    def preload_async(self) -> None:
        threading.Thread(target=self._load, daemon=True, name="ocr-preload").start()

    def _load(self) -> None:
        if self._engine is not None:
            return
        with self._load_lock:
            if self._engine is not None:
                return
            self.signals.state_changed.emit(True, "正在加载识别引擎…")
            try:
                # 新版 RapidOCR（PP-OCRv6，更快更准；截图文字均为正立，关闭方向分类提速）
                from rapidocr import RapidOCR

                self._engine = RapidOCR(
                    params={"Global.use_cls": False, "Global.log_level": "error"}
                )
                self._api = "v6"
            except Exception as e:
                # 兜底：老版 rapidocr_onnxruntime（PP-OCRv3）
                try:
                    from rapidocr_onnxruntime import RapidOCR

                    self._engine = RapidOCR(use_angle_cls=False, det_model_path="")
                    self._api = "v3"
                except Exception:
                    self._engine = None
                    self._load_error = f"识别引擎加载失败：{e}"
            self.signals.state_changed.emit(False, "")

    def ensure_loaded(self) -> None:
        if self._engine is None:
            self._load()

    @property
    def ready(self) -> bool:
        return self._engine is not None

    # ---------- 识别 ----------
    def recognize_async(self, job_id: str, image_path: str) -> None:
        threading.Thread(
            target=self._run, args=(job_id, image_path), daemon=True, name=f"ocr-{job_id}"
        ).start()

    def _run(self, job_id: str, image_path: str) -> None:
        try:
            items = self.recognize_sync(image_path)
            self.signals.finished.emit(job_id, items)
        except Exception as e:
            self.signals.failed.emit(job_id, f"识别失败：{e}")

    def recognize_sync(self, image_path: str, min_score: float = 0.35) -> list[dict]:
        """同步识别（测试与后台线程使用）。返回 [{box, text, score}]。"""
        self.ensure_loaded()
        if self._engine is None:
            raise RuntimeError(self._load_error or "OCR 引擎不可用")
        with self._lock:
            result = self._engine(image_path)
        raw = self._parse_result(result, min_score)
        # 按位置排序：先按上边界，再按 x
        def sort_key(it):
            ys = [p[1] for p in it["box"]]
            xs = [p[0] for p in it["box"]]
            return (min(ys), min(xs))
        raw.sort(key=sort_key)
        return raw

    def _parse_result(self, result, min_score: float) -> list[dict]:
        """兼容新版 RapidOCROutput 与老版 (lines, elapse) 两种结果。"""
        items = []
        if hasattr(result, "txts"):  # 新版 rapidocr (PP-OCRv6)
            boxes = getattr(result, "boxes", None)
            scores = getattr(result, "scores", None)
            for i, text in enumerate(result.txts):
                try:
                    score = float(scores[i]) if scores is not None else 1.0
                except Exception:
                    score = 1.0
                if score < min_score:
                    continue
                box = None
                if boxes is not None and i < len(boxes):
                    box = [[float(x), float(y)] for x, y in boxes[i]]
                items.append({"box": box or [], "text": str(text), "score": score})
            return items
        for line in (result or []):
            try:
                box, text, score = line[0], line[1], float(line[2])
            except Exception:
                continue
            if score < min_score:
                continue
            items.append({
                "box": [[float(x), float(y)] for x, y in box],
                "text": str(text),
                "score": score,
            })
        return items
