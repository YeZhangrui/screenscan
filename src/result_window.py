"""识别结果窗口：文字列表 + 图片预览 + 复制/导出/抠图/置顶。"""
from __future__ import annotations

import time

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import capture as cap
from .config import Config
from .widgets import ImageArea


class ResultWindow(QWidget):
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self._config = config
        self._plain: QPixmap | None = None   # 原图（dpr=1）
        self._items: list[dict] = []
        self._mode = ""
        self._last_extract: QPixmap | None = None
        self._pinned = bool(config.get("pin_result", True))
        self.setWindowTitle("识别结果 — 屏幕扫描助手")
        self.resize(900, 580)
        self._build_ui()
        self._apply_pin(self._pinned, silent=True)

    # ---------- UI ----------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.btn_copy_all = QPushButton("复制全部文字")
        self.btn_copy_all.clicked.connect(self.copy_all_text)
        self.btn_export = QPushButton("导出 .txt")
        self.btn_export.clicked.connect(self.export_txt)
        self.btn_copy_img = QPushButton("复制图片")
        self.btn_copy_img.clicked.connect(self.copy_image)
        self.btn_save_img = QPushButton("保存图片")
        self.btn_save_img.clicked.connect(self.save_image)
        self.btn_extract = QPushButton("提取图中图片")
        self.btn_extract.setCheckable(True)
        self.btn_extract.toggled.connect(self._on_extract_toggled)
        self.btn_pin = QPushButton("置顶")
        self.btn_pin.setCheckable(True)
        self.btn_pin.setChecked(self._pinned)
        self.btn_pin.toggled.connect(self._on_pin_toggled)
        for b in (self.btn_copy_all, self.btn_export, self.btn_copy_img,
                  self.btn_save_img, self.btn_extract, self.btn_pin):
            b.setProperty("role", "ghost")
            top.addWidget(b)
        top.addStretch(1)
        root.addLayout(top)

        center = QHBoxLayout()
        center.setSpacing(10)
        self.image_area = ImageArea()
        self.image_area.rect_selected.connect(self._on_extract_rect)
        self.listw = QListWidget()
        self.listw.setMinimumWidth(280)
        self.listw.itemDoubleClicked.connect(lambda item: self.copy_line(item.text()))
        self.listw.setToolTip("双击一行文字即可复制")
        center.addWidget(self.image_area, 3)
        center.addWidget(self.listw, 2)
        root.addLayout(center, 1)

        self.label_status = QLabel("")
        self.label_status.setStyleSheet("color: #5C7A99;")
        root.addWidget(self.label_status)

    # ---------- 展示结果 ----------
    def show_result(self, pixmap: QPixmap, items: list[dict], mode: str,
                    text_lines: list[str] | None = None) -> None:
        plain = pixmap.copy()
        plain.setDevicePixelRatio(1.0)
        self._plain = plain
        self._items = items
        self._mode = mode
        self._last_extract = None
        # 预览：画识别框
        self.image_area.set_source(cap.draw_boxes(plain, items))
        # 文字列表
        self.listw.clear()
        if items:
            for i, it in enumerate(items, 1):
                self.listw.addItem(f"{i}. {it['text']}")
            self.label_status.setText(
                f"识别到 {len(items)} 段文字（点击一行或双击即可复制）"
            )
        elif text_lines:
            for line in text_lines:
                if line.strip():
                    self.listw.addItem(line)
            self.label_status.setText("历史记录：文本已加载")
        else:
            self.label_status.setText("未识别到文字，可尝试框选更大范围或放大图片")
        self.setWindowTitle(f"识别结果 · {mode} — 屏幕扫描助手")
        self.show()
        self.raise_()
        self.activateWindow()

    def _apply_pin(self, pinned: bool, silent: bool = False) -> None:
        self._pinned = pinned
        self.setWindowFlag(Qt.WindowStaysOnTopHint, pinned)
        self.btn_pin.setChecked(pinned)
        if not silent:
            self.show()

    # ---------- 文字 ----------
    def full_text(self) -> str:
        if self._items:
            return "\n".join(it["text"] for it in self._items)
        texts = [self.listw.item(i).text() for i in range(self.listw.count())]
        return "\n".join(texts)

    def copy_all_text(self) -> None:
        text = self.full_text()
        if not text:
            self.label_status.setText("暂无可复制的文字")
            return
        QGuiApplication.clipboard().setText(text)
        self.label_status.setText("已复制全部文字 ✓")

    def copy_line(self, line: str) -> None:
        # 去掉 "1. " 前缀
        text = line
        for sep in (". ", "．", " "):
            idx = text.find(sep)
            if idx == 1:
                text = text[2:]
                break
        QGuiApplication.clipboard().setText(text)
        self.label_status.setText(f"已复制：{text[:40]}")

    def export_txt(self) -> None:
        text = self.full_text()
        from PySide6.QtWidgets import QFileDialog
        from .config import APP_TITLE

        default = f"识别结果_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        path, _ = QFileDialog.getSaveFileName(self, "导出识别结果", default, "文本文件 (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self.label_status.setText(f"已导出：{path}")
        except OSError as e:
            QMessageBox.warning(self, APP_TITLE, f"导出失败：{e}")

    # ---------- 图片 ----------
    def copy_image(self) -> None:
        if self._plain is None:
            return
        QGuiApplication.clipboard().setImage(self._plain.toImage())
        self.label_status.setText("已复制图片 ✓（可粘贴到微信/QQ/Word 等）")

    def save_image(self) -> None:
        if self._plain is None:
            return
        from PySide6.QtWidgets import QFileDialog
        from .config import APP_TITLE

        default = f"截图_{time.strftime('%Y%m%d_%H%M%S')}.png"
        path, _ = QFileDialog.getSaveFileName(self, "保存图片", default, "PNG 图片 (*.png)")
        if not path:
            return
        if self._plain.save(path, "PNG"):
            self.label_status.setText(f"已保存：{path}")
        else:
            QMessageBox.warning(self, APP_TITLE, "保存失败，请更换路径")

    # ---------- 提取图中图片 ----------
    def _on_extract_toggled(self, on: bool) -> None:
        self.image_area.set_selection_mode(on)
        if on:
            self.label_status.setText("提取模式：先在左侧图片上按住左键拖动，框选要提取的图片区域")

    def _on_extract_rect(self, rect: QRect) -> None:
        if self._plain is None:
            return
        crop = self._plain.copy(rect)
        self._last_extract = crop
        QGuiApplication.clipboard().setImage(crop.toImage())
        self.label_status.setText(
            f"已提取并复制图片区域（{crop.width()}×{crop.height()}）✓"
        )
        # 退出框选模式，避免误操作
        self.btn_extract.setChecked(False)

    # ---------- 置顶 ----------
    def _on_pin_toggled(self, on: bool) -> None:
        self._config.set("pin_result", bool(on))
        self._apply_pin(on)

    def ensure_pin(self) -> None:
        self._apply_pin(bool(self._config.get("pin_result", True)))
