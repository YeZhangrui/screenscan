"""设置窗口：快捷键、置顶、开机自启。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from . import autostart
from .config import APP_TITLE, Config
from .hotkeys import is_valid_hotkey
from .theme import MODE_DARK, MODE_LABELS, MODE_LIGHT, MODE_SYSTEM

PRESETS = ["alt+s", "alt+shift+s", "ctrl+alt+s", "ctrl+s", "f9", "f10", "alt+f9"]


class SettingsDialog(QDialog):
    def __init__(
        self,
        config: Config,
        hotkey_apply_cb,   # (capture, fullscreen) -> str | None
        parent=None,
    ):
        super().__init__(parent)
        self._config = config
        self._apply_cb = hotkey_apply_cb
        self.setWindowTitle("设置 — 屏幕扫描助手")
        self.setModal(True)
        self.resize(540, 320)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(12)

        self.combo_capture = QComboBox()
        self.combo_capture.setEditable(True)
        self.combo_capture.addItems(PRESETS)
        self.combo_capture.setCurrentText(str(self._config.get("hotkey_capture", "alt+s")))

        self.combo_full = QComboBox()
        self.combo_full.setEditable(True)
        self.combo_full.addItems([p for p in PRESETS if p != "alt+shift+s"] + ["alt+shift+s"])
        self.combo_full.setCurrentText(str(self._config.get("hotkey_fullscreen", "alt+shift+s")))

        form.addRow("框选识别快捷键：", self.combo_capture)
        form.addRow("全屏扫描快捷键：", self.combo_full)

        self.chk_pin = QCheckBox("识别结果窗口自动置顶（可随时关）")
        self.chk_pin.setChecked(bool(self._config.get("pin_result", True)))
        self.chk_auto = QCheckBox("开机自动启动（后台待命）")
        self.chk_auto.setChecked(autostart.is_enabled())

        form.addRow("", self.chk_pin)
        form.addRow("", self.chk_auto)

        # 主题模式
        theme_row = QHBoxLayout()
        theme_row.setSpacing(14)
        self.theme_group = QButtonGroup(self)
        self.theme_buttons = {}
        current_theme = str(self._config.get("theme", MODE_SYSTEM)).lower()
        for mode in (MODE_SYSTEM, MODE_LIGHT, MODE_DARK):
            btn = QRadioButton(MODE_LABELS[mode])
            btn.setChecked(current_theme == mode)
            self.theme_group.addButton(btn)
            self.theme_buttons[mode] = btn
            theme_row.addWidget(btn)
        theme_row.addStretch(1)
        form.addRow("主题模式：", theme_row)

        root.addLayout(form)

        self.label_hint = QLabel(
            "快捷键写法示例：alt+s、ctrl+alt+s、alt+shift+s、f9（支持 Alt / Ctrl / Shift / Win 组合与 F1-F12）"
        )
        self.label_hint.setObjectName("Subtitle")
        self.label_hint.setWordWrap(True)
        root.addWidget(self.label_hint)

        self.label_error = QLabel("")
        self.label_error.setObjectName("ErrorLabel")
        root.addWidget(self.label_error)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("保存")
        btn_save.setProperty("role", "primary")
        btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        root.addLayout(btn_row)

    def selected_theme(self) -> str:
        """当前选中的主题模式。"""
        for mode, btn in self.theme_buttons.items():
            if btn.isChecked():
                return mode
        return MODE_SYSTEM

    def _on_save(self) -> None:
        capture = self.combo_capture.currentText().strip()
        full = self.combo_full.currentText().strip()
        for name, val in (("框选识别", capture), ("全屏扫描", full)):
            if not is_valid_hotkey(val):
                self.label_error.setText(f"「{name}」快捷键写法无效：{val}")
                return
        if capture == full:
            self.label_error.setText("两个快捷键不能相同")
            return
        err = self._apply_cb(capture, full)
        if err:
            self.label_error.setText(err)
            return
        self._config.set("hotkey_capture", capture)
        self._config.set("hotkey_fullscreen", full)
        self._config.set("pin_result", self.chk_pin.isChecked())
        self._config.set("theme", self.selected_theme())
        if not autostart.set_enabled(self.chk_auto.isChecked()):
            QMessageBox.warning(self, APP_TITLE, "开机自启设置写入失败（可能被系统限制）")
        self.accept()
