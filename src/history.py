"""识别历史记录：本地 json 索引 + png 截图/缩略图。"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from .config import data_dir

THUMB_MAX_W = 360
THUMB_MAX_H = 240


class HistoryStore:
    def __init__(self, root: Path | None = None, limit: int = 50):
        self.dir = Path(root) if root else data_dir() / "history"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.dir / "index.json"
        self.limit = limit

    # ---------- 内部 ----------
    def _load(self) -> list[dict]:
        try:
            data = json.loads(self.index_file.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save(self, records: list[dict]) -> None:
        self.index_file.write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _thumb(pixmap: QPixmap) -> QPixmap:
        if pixmap.width() <= THUMB_MAX_W and pixmap.height() <= THUMB_MAX_H:
            return pixmap.copy()
        return pixmap.scaled(
            THUMB_MAX_W, THUMB_MAX_H, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

    # ---------- 对外 ----------
    def add(self, mode: str, text: str, pixmap: QPixmap) -> dict:
        rid = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}"
        image_name = f"{rid}.png"
        thumb_name = f"{rid}_thumb.png"
        plain = pixmap.copy()
        plain.setDevicePixelRatio(1.0)
        plain.save(str(self.dir / image_name), "PNG")
        self._thumb(plain).save(str(self.dir / thumb_name), "PNG")
        records = self._load()
        records.insert(0, {
            "id": rid,
            "ts": time.time(),
            "mode": mode,
            "text": text,
            "image": image_name,
            "thumb": thumb_name,
        })
        records = records[: self.limit]
        self._prune_orphans(records)
        self._save(records)
        return records[0]

    def _prune_orphans(self, records: list[dict]) -> None:
        keep = set()
        for r in records:
            keep.add(r.get("image", ""))
            keep.add(r.get("thumb", ""))
        for f in self.dir.glob("*.png"):
            if f.name not in keep:
                try:
                    f.unlink()
                except OSError:
                    pass

    def list(self) -> list[dict]:
        return self._load()

    def get(self, rid: str) -> dict | None:
        for r in self._load():
            if r.get("id") == rid:
                return r
        return None

    def delete(self, rid: str) -> None:
        records = self._load()
        records = [r for r in records if r.get("id") != rid]
        self._prune_orphans(records)
        self._save(records)

    def clear(self) -> None:
        for f in self.dir.glob("*.png"):
            try:
                f.unlink()
            except OSError:
                pass
        self._save([])

    def resolve(self, name: str) -> Path:
        return self.dir / name
