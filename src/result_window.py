"""识别结果窗口：文字列表（支持多选/勾选）+ 图片预览 + 复制/导出/抠图/置顶。"""
from __future__ import annotations

import time

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import capture as cap
from .config import APP_TITLE, Config
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
        self.resize(940, 620)
        self._build_ui()
        self._apply_pin(self._pinned, silent=True)

    # ---------- UI ----------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # 第一行：文字相关操作
        row_text = QHBoxLayout()
        row_text.setSpacing(8)
        self.btn_copy_all = QPushButton("复制全部文字")
        self.btn_copy_all.clicked.connect(self.copy_all_text)
        self.btn_copy_selected = QPushButton("复制选中")
        self.btn_copy_selected.clicked.connect(self.copy_selected)
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.setCheckable(True)
        self.btn_select_all.clicked.connect(self.toggle_select_all)
        self.btn_export = QPushButton("导出 .txt")
        self.btn_export.clicked.connect(self.export_txt)
        for b in (self.btn_copy_all, self.btn_copy_selected, self.btn_select_all, self.btn_export):
            b.setProperty("role", "ghost")
            row_text.addWidget(b)
        row_text.addStretch(1)
        root.addLayout(row_text)

        # 第二行：图片相关操作
        row_img = QHBoxLayout()
        row_img.setSpacing(8)
        self.btn_copy_img = QPushButton("复制图片")
        self.btn_copy_img.clicked.connect(self.copy_image)
        self.btn_save_img = QPushButton("保存图片")
        self.btn_save_img.clicked.connect(self.save_image)
        self.btn_extract = QPushButton("提取图中图片")
        self.btn_extract.setCheckable(True)
        self.btn_extract.toggled.connect(self._on_extract_toggled)
        self.btn_save_extract = QPushButton("保存提取图片")
        self.btn_save_extract.setEnabled(False)
        self.btn_save_extract.clicked.connect(self.save_extract)
        self.btn_pin = QPushButton("置顶")
        self.btn_pin.setCheckable(True)
        self.btn_pin.setChecked(self._pinned)
        self.btn_pin.toggled.connect(self._on_pin_toggled)
        for b in (self.btn_copy_img, self.btn_save_img, self.btn_extract,
                  self.btn_save_extract, self.btn_pin):
            b.setProperty("role", "ghost")
            row_img.addWidget(b)
        row_img.addStretch(1)
        root.addLayout(row_img)

        center = QHBoxLayout()
        center.setSpacing(10)
        self.image_area = ImageArea()
        self.image_area.rect_selected.connect(self._on_extract_rect)
        self.listw = QListWidget()
        self.listw.setMinimumWidth(300)
        self.listw.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.listw.itemDoubleClicked.connect(lambda item: self.copy_line(item.text()))
        self.listw.itemChanged.connect(self._on_item_changed)
        self.listw.setToolTip("勾选或按住 Ctrl/Shift 多选，点「复制选中」批量复制；双击单行复制")
        center.addWidget(self.image_area, 3)
        center.addWidget(self.listw, 2)
        root.addLayout(center, 1)

        self.label_status = QLabel("")
        self.label_status.setStyleSheet("color: #5C7A99;")
        root.addWidget(self.label_status)

        # Ctrl+C / Ctrl+Shift+C：一键复制全部文字
        self._shortcut_copy = QShortcut(QKeySequence("Ctrl+C"), self)
        self._shortcut_copy.activated.connect(self.copy_all_text)
        self._shortcut_copy2 = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
        self._shortcut_copy2.activated.connect(self.copy_selected)

    # ---------- 展示结果 ----------
    def show_result(self, pixmap: QPixmap, items: list[dict], mode: str,
                    text_lines: list[str] | None = None) -> None:
        plain = pixmap.copy()
        plain.setDevicePixelRatio(1.0)
        self._plain = plain
        self._items = items
        self._mode = mode
        self._last_extract = None
        self.btn_save_extract.setEnabled(False)
        # 预览：画识别框
        self.image_area.set_source(cap.draw_boxes(plain, items))
        # 文字列表（可勾选）
        self.listw.blockSignals(True)
        self.listw.clear()
        texts = [it["text"] for it in items] if items else (text_lines or [])
        texts = [t for t in texts if str(t).strip()]
        for i, t in enumerate(texts, 1):
            item = QListWidgetItem(f"{i}. {t}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.listw.addItem(item)
        self.listw.blockSignals(False)
        self.btn_select_all.setChecked(False)
        self.btn_select_all.setText("全选")
        if texts:
            self.label_status.setText(
                f"识别到 {len(texts)} 段文字（勾选或 Ctrl/Shift 多选后点「复制选中」，双击单行即可复制）"
            )
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
    def _clean(self, line: str) -> str:
        """去掉列表里的 '1. ' 前缀。"""
        idx = line.find(". ")
        if idx in (1, 2):  # 支持 1. / 12.
            return line[idx + 2:]
        return line

    def all_texts(self) -> list[str]:
        if self._items:
            return [it["text"] for it in self._items if str(it["text"]).strip()]
        return [self._clean(self.listw.item(i).text()) for i in range(self.listw.count())]

    def selected_texts(self) -> list[str]:
        """已勾选的文字（按列表顺序）；没有勾选时回退到当前多选行。"""
        checked = [
            self._clean(self.listw.item(i).text())
            for i in range(self.listw.count())
            if self.listw.item(i).checkState() == Qt.Checked
        ]
        if checked:
            return checked
        return [self._clean(it.text()) for it in self.listw.selectedItems()]

    def full_text(self) -> str:
        return "\n".join(self.all_texts())

    def copy_all_text(self) -> None:
        text = self.full_text()
        if not text:
            self.label_status.setText("暂无可复制的文字")
            return
        QGuiApplication.clipboard().setText(text)
        self.label_status.setText(f"已复制全部文字（{len(self.all_texts())} 段）✓")

    def copy_selected(self) -> None:
        texts = self.selected_texts()
        if not texts:
            self.label_status.setText("请先勾选或选中要复制的文字（可按住 Ctrl/Shift 多选）")
            return
        QGuiApplication.clipboard().setText("\n".join(texts))
        self.label_status.setText(f"已复制选中的 {len(texts)} 段文字 ✓")

    def toggle_select_all(self, checked: bool) -> None:
        self.listw.blockSignals(True)
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(self.listw.count()):
            self.listw.item(i).setCheckState(state)
        self.listw.blockSignals(False)
        self.btn_select_all.setText("取消全选" if checked else "全选")
        self._on_item_changed(None)

    def _on_item_changed(self, item) -> None:
        count = sum(
            1 for i in range(self.listw.count())
            if self.listw.item(i).checkState() == Qt.Checked
        )
        if count:
            self.label_status.setText(f"已勾选 {count} 段文字，点「复制选中」批量复制")
        elif self.listw.count():
            self.label_status.setText(
                f"识别到 {self.listw.count()} 段文字（勾选或 Ctrl/Shift 多选后点「复制选中」）"
            )

    def copy_line(self, line: str) -> None:
        text = self._clean(line)
        QGuiApplication.clipboard().setText(text)
        self.label_status.setText(f"已复制：{text[:40]}")

    def export_txt(self) -> None:
        texts = self.selected_texts()
        scope = "选中"
        if not texts:
            texts = self.all_texts()
            scope = "全部"
        default = f"识别结果_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        path, _ = QFileDialog.getSaveFileName(self, "导出识别结果", default, "文本文件 (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(texts))
            self.label_status.setText(f"已导出{scope} {len(texts)} 段文字：{path}")
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
        self.btn_save_extract.setEnabled(True)
        self.label_status.setText(
            f"已提取并复制图片区域（{crop.width()}×{crop.height()}）✓ 可点「保存提取图片」存为文件"
        )
        self.btn_extract.setChecked(False)

    def save_extract(self) -> None:
        if self._last_extract is None:
            return
        default = f"提取图片_{time.strftime('%Y%m%d_%H%M%S')}.png"
        path, _ = QFileDialog.getSaveFileName(self, "保存提取的图片", default, "PNG 图片 (*.png)")
        if not path:
            return
        if self._last_extract.save(path, "PNG"):
            self.label_status.setText(f"已保存：{path}")
        else:
            QMessageBox.warning(self, APP_TITLE, "保存失败，请更换路径")

    # ---------- 置顶 ----------
    def _on_pin_toggled(self, on: bool) -> None:
        self._config.set("pin_result", bool(on))
        self._apply_pin(on)

    def ensure_pin(self) -> None:
        self._apply_pin(bool(self._config.get("pin_result", True)))
