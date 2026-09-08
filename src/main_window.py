"""主窗口：功能按钮 + 使用说明 + 历史记录。"""
from __future__ import annotations

import time

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .config import Config
from .history import HistoryStore
from .hotkeys import pretty_hotkey


class MainWindow(QMainWindow):
    capture_clicked = Signal()
    fullscreen_clicked = Signal()
    upload_clicked = Signal()
    settings_clicked = Signal()
    open_history = Signal(str)   # record id

    def __init__(self, config: Config, history: HistoryStore):
        super().__init__()
        self._config = config
        self._history = history
        self.setWindowTitle("屏幕扫描助手")
        self.resize(780, 580)
        self.setMinimumSize(640, 480)
        self._build_ui()
        self.refresh_hints()
        self.update_history()

    # ---------- UI ----------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        # 标题栏
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("屏幕扫描助手")
        title.setObjectName("Title")
        self.label_sub = QLabel("")
        self.label_sub.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(self.label_sub)
        header.addLayout(title_box)
        header.addStretch(1)
        self.btn_settings = QPushButton("⚙ 设置")
        self.btn_settings.setProperty("role", "ghost")
        self.btn_settings.clicked.connect(self.settings_clicked.emit)
        header.addWidget(self.btn_settings)
        root.addLayout(header)

        # 功能按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.btn_capture = QPushButton("✂ 框选识别")
        self.btn_capture.setProperty("role", "primary")
        self.btn_capture.clicked.connect(self.capture_clicked.emit)
        self.btn_full = QPushButton("⛶ 全屏扫描")
        self.btn_full.setProperty("role", "primary")
        self.btn_full.clicked.connect(self.fullscreen_clicked.emit)
        self.btn_upload = QPushButton("🖼 上传图片识别")
        self.btn_upload.setProperty("role", "primary")
        self.btn_upload.clicked.connect(self.upload_clicked.emit)
        for b in (self.btn_capture, self.btn_full, self.btn_upload):
            btn_row.addWidget(b, 1)
        root.addLayout(btn_row)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_guide_tab(), "使用说明")
        self.tabs.addTab(self._build_history_tab(), "历史记录")
        root.addWidget(self.tabs, 1)

        # 状态栏
        self.label_status = QLabel("就绪")
        self.label_status.setStyleSheet("color: #5C7A99;")
        root.addWidget(self.label_status)

    def _build_guide_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        class Card(QWidget):
            def __init__(self, text: str):
                super().__init__()
                self.setObjectName("Card")
                l = QVBoxLayout(self)
                l.setContentsMargins(16, 14, 16, 14)
                lab = QLabel(text)
                lab.setWordWrap(True)
                l.addWidget(lab)

        lay.addWidget(Card(
            "【框选识别】\n"
            "按快捷键（默认 Alt+S）或点击「框选识别」→ 界面自动隐藏 → 屏幕出现暗色遮罩\n"
            "按住鼠标左键拖动，框选要识别的区域 → 松开后自动识别，结果弹窗可复制文字/图片。\n"
            "取消：按 Esc 或点鼠标右键。"
        ))
        lay.addWidget(Card(
            "【全屏扫描】\n"
            "点击「全屏扫描」或按快捷键（默认 Alt+Shift+S）→ 自动识别整个屏幕上的文字，\n"
            "识别结果中会标出每段文字的位置。"
        ))
        lay.addWidget(Card(
            "【上传图片识别】\n"
            "点击「上传图片识别」选择本地图片文件 → 识别图片中的文字，同样可复制文字、\n"
            "复制图片，或在结果窗内框选提取某块图片区域。"
        ))
        hint = QLabel("所有识别均在本地完成，内容不会上传到网络，断网也能使用。")
        hint.setObjectName("Subtitle")
        lay.addWidget(hint)
        lay.addStretch(1)
        return w

    def _build_history_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(
            lambda item: self.open_history.emit(item.data(Qt.UserRole))
        )
        self.history_list.setToolTip("双击一条记录可重新查看结果")
        btn_row = QHBoxLayout()
        self.btn_open = QPushButton("打开所选")
        self.btn_open.setProperty("role", "ghost")
        self.btn_open.clicked.connect(
            lambda: self.open_history.emit(
                self._current_history_id() or ""
            )
        )
        self.btn_del = QPushButton("删除所选")
        self.btn_del.setProperty("role", "danger")
        self.btn_del.clicked.connect(self._delete_selected)
        self.btn_clear = QPushButton("清空历史")
        self.btn_clear.setProperty("role", "danger")
        self.btn_clear.clicked.connect(self._clear_history)
        btn_row.addWidget(self.btn_open)
        btn_row.addWidget(self.btn_del)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_clear)
        lay.addWidget(self.history_list, 1)
        lay.addLayout(btn_row)
        return w

    # ---------- 数据 ----------
    def refresh_hints(self) -> None:
        cap = pretty_hotkey(str(self._config.get("hotkey_capture", "alt+s")))
        full = pretty_hotkey(str(self._config.get("hotkey_fullscreen", "alt+shift+s")))
        self.label_sub.setText(
            f"快捷键：{cap} 框选识别 · {full} 全屏扫描 · 点击托盘图标显示/隐藏窗口"
        )
        self.btn_capture.setToolTip(f"快捷键：{cap}")
        self.btn_full.setToolTip(f"快捷键：{full}")

    def update_history(self) -> None:
        self.history_list.clear()
        records = self._history.list()
        if not records:
            item = self._empty_item("暂无历史记录 — 完成一次识别后自动保存")
            return
        for r in records:
            when = time.strftime("%m-%d %H:%M", time.localtime(r.get("ts", 0)))
            text = (r.get("text") or "").replace("\n", " / ")
            if len(text) > 60:
                text = text[:60] + "…"
            item_text = f"{when}  [{r.get('mode', '')}]  {text or '（无文字）'}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, r.get("id", ""))
            self.history_list.addItem(item)

    @staticmethod
    def _empty_item(text: str) -> QListWidgetItem:
        item = QListWidgetItem(text)
        item.setFlags(Qt.NoItemFlags)
        return item

    def _current_history_id(self) -> str | None:
        item = self.history_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _delete_selected(self) -> None:
        rid = self._current_history_id()
        if rid:
            self._history.delete(rid)
            self.update_history()

    def _clear_history(self) -> None:
        self._history.clear()
        self.update_history()

    # ---------- 状态 ----------
    def set_engine_state(self, loading: bool, msg: str = "") -> None:
        if loading:
            self.label_status.setText("识别引擎加载中，稍等片刻即可使用…")
        else:
            self.label_status.setText("识别引擎就绪 ✓")

    def set_busy(self, msg: str) -> None:
        self.label_status.setText(msg)

    def show_events(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
