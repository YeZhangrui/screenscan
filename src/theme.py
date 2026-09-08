"""淡蓝色主题（QSS）。"""
from __future__ import annotations

from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication

# —— 调色板（淡蓝主题）——
BG = "#EAF3FB"            # 窗口背景：淡蓝
CARD = "#FFFFFF"          # 卡片
PRIMARY = "#2F80D6"       # 主蓝
PRIMARY_HOVER = "#2A6FB8"
PRIMARY_PRESSED = "#3E8FDE"
BORDER = "#CFE3F5"
TEXT = "#1F3A5F"
MUTED = "#5C7A99"
LIGHT = "#BFE0F8"

QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QDialog {{
    background: {BG};
}}
QWidget#Card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QLabel#Title {{
    font-size: 20px;
    font-weight: bold;
    color: {PRIMARY};
}}
QLabel#Subtitle {{
    color: {MUTED};
    font-size: 12px;
}}

/* —— 按钮 —— */
QPushButton {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 16px;
}}
QPushButton:hover {{ background: #F4FAFF; border-color: {LIGHT}; }}
QPushButton:pressed {{ background: #E4F1FC; }}
QPushButton:disabled {{ color: #A8BBD0; background: #F2F7FC; }}

QPushButton[role="primary"] {{
    background: {PRIMARY};
    color: white;
    border: none;
    font-size: 14px;
    font-weight: bold;
    padding: 12px 24px;
}}
QPushButton[role="primary"]:hover {{ background: {PRIMARY_HOVER}; }}
QPushButton[role="primary"]:pressed {{ background: {PRIMARY_PRESSED}; }}
QPushButton[role="primary"]:disabled {{ background: #A9C9EC; color: #F2F7FC; }}

QPushButton[role="ghost"] {{
    background: transparent;
    border: 1px solid {BORDER};
    color: {PRIMARY};
    padding: 6px 12px;
    border-radius: 6px;
}}
QPushButton[role="ghost"]:hover {{ background: #EAF3FB; }}

QPushButton[role="danger"] {{
    background: #FDF3F3;
    color: #C0504D;
    border: 1px solid #F2D7D7;
}}
QPushButton[role="danger"]:hover {{ background: #FAE7E7; }}

/* —— 列表 / 输入 —— */
QListWidget, QTextEdit, QLineEdit, QComboBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {LIGHT};
    selection-color: {TEXT};
}}
QListWidget::item {{ padding: 6px; border-radius: 5px; }}
QListWidget::item:selected {{ background: {LIGHT}; }}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{ border-color: {PRIMARY}; }}

/* —— 标签页 —— */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {CARD};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    color: {MUTED};
}}
QTabBar::tab:selected {{
    background: {CARD};
    color: {PRIMARY};
    font-weight: bold;
    border: 1px solid {BORDER};
    border-bottom: none;
}}

/* —— 复选 / 开关 —— */
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {CARD};
}}
QCheckBox::indicator:checked {{ background: {PRIMARY}; border-color: {PRIMARY}; }}

/* —— 滚动条 —— */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #B9D7F2; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {PRIMARY}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #B9D7F2; border-radius: 5px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: {PRIMARY}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QToolTip {{
    background: {TEXT};
    color: white;
    border: none;
    padding: 6px 10px;
    border-radius: 6px;
}}
QMenu {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{ padding: 6px 24px; border-radius: 6px; }}
QMenu::item:selected {{ background: {LIGHT}; color: {PRIMARY}; }}
QStatusBar {{ background: transparent; color: {MUTED}; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyleSheet(QSS)
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BG))
    palette.setColor(QPalette.Base, QColor(CARD))
    palette.setColor(QPalette.Button, QColor(CARD))
    palette.setColor(QPalette.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.Highlight, QColor(LIGHT))
    palette.setColor(QPalette.HighlightedText, QColor(TEXT))
    app.setPalette(palette)
