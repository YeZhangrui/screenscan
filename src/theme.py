"""主题系统：浅色 / 深色 / 跟随系统 三种模式，调色板驱动 + 统一样式表。

- 浅色：淡蓝简洁风（默认）
- 深色：深蓝灰，夜间/暗色桌面更护眼
- 跟随系统：读取 Windows 应用主题（Qt colorScheme），系统切换时自动跟随
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

MODE_SYSTEM = "system"
MODE_LIGHT = "light"
MODE_DARK = "dark"
THEME_MODES = (MODE_SYSTEM, MODE_LIGHT, MODE_DARK)

MODE_LABELS = {
    MODE_SYSTEM: "跟随系统",
    MODE_LIGHT: "浅色",
    MODE_DARK: "深色",
}


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str            # 窗口背景
    card: str          # 卡片/输入框背景
    card_alt: str      # 次级卡片（悬停底色）
    primary: str       # 主色
    primary_hover: str
    primary_pressed: str
    primary_disabled: str
    border: str
    border_strong: str
    text: str
    muted: str
    selection: str     # 选中底色
    selection_text: str
    danger_bg: str
    danger_border: str
    danger_text: str
    scroll: str
    scroll_hover: str


LIGHT = Palette(
    name=MODE_LIGHT,
    bg="#EAF3FB",
    card="#FFFFFF",
    card_alt="#F4FAFF",
    primary="#2F80D6",
    primary_hover="#2A6FB8",
    primary_pressed="#3E8FDE",
    primary_disabled="#A9C9EC",
    border="#CFE3F5",
    border_strong="#BFE0F8",
    text="#1F3A5F",
    muted="#5C7A99",
    selection="#BFE0F8",
    selection_text="#1F3A5F",
    danger_bg="#FDF3F3",
    danger_border="#F2D7D7",
    danger_text="#C0504D",
    scroll="#B9D7F2",
    scroll_hover="#2F80D6",
)

DARK = Palette(
    name=MODE_DARK,
    bg="#161E28",
    card="#1F2A38",
    card_alt="#273447",
    primary="#4A9BE8",
    primary_hover="#5FAEF5",
    primary_pressed="#3D8AD6",
    primary_disabled="#38536F",
    border="#2E4054",
    border_strong="#3C5872",
    text="#E6EEF7",
    muted="#94A9C0",
    selection="#2E4A6B",
    selection_text="#EAF3FB",
    danger_bg="#3A2A2C",
    danger_border="#5A3A3E",
    danger_text="#F09A9A",
    scroll="#3B526B",
    scroll_hover="#4A9BE8",
)

_PALETTES = {MODE_LIGHT: LIGHT, MODE_DARK: DARK}


def qss(p: Palette) -> str:
    return f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
    color: {p.text};
}}
QMainWindow, QDialog {{ background: {p.bg}; }}
QWidget {{ color: {p.text}; }}

QWidget#Card {{
    background: {p.card};
    border: 1px solid {p.border};
    border-radius: 10px;
}}
QLabel#Title {{
    font-size: 20px;
    font-weight: bold;
    color: {p.primary};
}}
QLabel#Subtitle, QLabel#StatusLabel {{ color: {p.muted}; }}
QLabel#ErrorLabel {{ color: {p.danger_text}; }}
QLabel#ImageArea {{
    background: {p.card};
    border: 1px solid {p.border};
    border-radius: 8px;
}}

/* —— 按钮 —— */
QPushButton {{
    background: {p.card};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 8px 16px;
    color: {p.text};
}}
QPushButton:hover {{ background: {p.card_alt}; border-color: {p.border_strong}; }}
QPushButton:pressed {{ background: {p.selection}; }}
QPushButton:disabled {{ color: {p.muted}; background: {p.card_alt}; }}

QPushButton[role="primary"] {{
    background: {p.primary};
    color: #FFFFFF;
    border: none;
    font-size: 14px;
    font-weight: bold;
    padding: 12px 24px;
}}
QPushButton[role="primary"]:hover {{ background: {p.primary_hover}; }}
QPushButton[role="primary"]:pressed {{ background: {p.primary_pressed}; }}
QPushButton[role="primary"]:disabled {{ background: {p.primary_disabled}; color: {p.bg}; }}

QPushButton[role="ghost"] {{
    background: transparent;
    border: 1px solid {p.border};
    color: {p.primary};
    padding: 6px 12px;
    border-radius: 6px;
}}
QPushButton[role="ghost"]:hover {{ background: {p.card_alt}; border-color: {p.border_strong}; }}
QPushButton[role="ghost"]:checked {{
    background: {p.selection};
    border-color: {p.primary};
    color: {p.selection_text};
}}

QPushButton[role="danger"] {{
    background: {p.danger_bg};
    color: {p.danger_text};
    border: 1px solid {p.danger_border};
}}
QPushButton[role="danger"]:hover {{ border-color: {p.danger_text}; }}

/* —— 列表 / 输入 —— */
QListWidget, QTextEdit, QLineEdit, QComboBox {{
    background: {p.card};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 4px;
    color: {p.text};
    selection-background-color: {p.selection};
    selection-color: {p.selection_text};
}}
QListWidget::item {{ padding: 7px 6px; border-radius: 6px; }}
QListWidget::item:hover {{ background: {p.card_alt}; }}
QListWidget::item:selected {{ background: {p.selection}; color: {p.selection_text}; }}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QListWidget:focus {{
    border-color: {p.primary};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {p.card};
    border: 1px solid {p.border};
    selection-background-color: {p.selection};
    selection-color: {p.selection_text};
    outline: none;
}}

/* —— 标签页 —— */
QTabWidget::pane {{
    border: 1px solid {p.border};
    border-radius: 10px;
    background: {p.card};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    padding: 9px 20px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    color: {p.muted};
}}
QTabBar::tab:hover {{ color: {p.primary}; }}
QTabBar::tab:selected {{
    background: {p.card};
    color: {p.primary};
    font-weight: bold;
    border: 1px solid {p.border};
    border-bottom: none;
}}

/* —— 复选 / 单选 —— */
QCheckBox, QRadioButton {{ spacing: 8px; color: {p.text}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {p.border_strong};
    border-radius: 4px;
    background: {p.card};
}}
QCheckBox::indicator:hover {{ border-color: {p.primary}; }}
QCheckBox::indicator:checked {{ background: {p.primary}; border-color: {p.primary}; }}
QRadioButton::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {p.border_strong};
    border-radius: 8px;
    background: {p.card};
}}
QRadioButton::indicator:hover {{ border-color: {p.primary}; }}
QRadioButton::indicator:checked {{
    background: {p.primary};
    border: 4px solid {p.card};
    outline: 1px solid {p.primary};
}}

/* —— 滚动条 —— */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.scroll}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p.scroll_hover}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p.scroll}; border-radius: 5px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: {p.scroll_hover}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QToolTip {{
    background: {p.text};
    color: {p.bg};
    border: none;
    padding: 6px 10px;
    border-radius: 6px;
}}
QMenu {{
    background: {p.card};
    border: 1px solid {p.border};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{ padding: 7px 26px; border-radius: 6px; color: {p.text}; }}
QMenu::item:selected {{ background: {p.selection}; color: {p.selection_text}; }}
QMenu::separator {{ height: 1px; background: {p.border}; margin: 4px 8px; }}
QStatusBar {{ background: transparent; color: {p.muted}; }}
QGroupBox {{
    border: 1px solid {p.border};
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: bold;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; color: {p.primary}; }}
"""


def system_is_dark(app: QApplication | None = None) -> bool:
    """读取系统深浅色设置（优先 Qt colorScheme，其次 Windows 注册表）。"""
    try:
        hints = (app or QApplication.instance()).styleHints()
        scheme = hints.colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except Exception:  # noqa: BLE001
        pass
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as k:
            value, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
            return int(value) == 0
    except Exception:  # noqa: BLE001
        return False


def resolve_mode(mode: str, app: QApplication | None = None) -> str:
    """把配置里的模式解析为实际生效的 light / dark。"""
    mode = (mode or MODE_SYSTEM).lower()
    if mode == MODE_LIGHT:
        return MODE_LIGHT
    if mode == MODE_DARK:
        return MODE_DARK
    return MODE_DARK if system_is_dark(app) else MODE_LIGHT


def palette_for(mode: str, app: QApplication | None = None) -> Palette:
    return _PALETTES[resolve_mode(mode, app)]


def apply_theme(app: QApplication, mode: str = MODE_SYSTEM) -> Palette:
    """应用主题（样式表 + 调色板），返回实际生效的调色板。"""
    p = palette_for(mode, app)
    app.setStyleSheet(qss(p))
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(p.bg))
    pal.setColor(QPalette.WindowText, QColor(p.text))
    pal.setColor(QPalette.Base, QColor(p.card))
    pal.setColor(QPalette.AlternateBase, QColor(p.card_alt))
    pal.setColor(QPalette.Text, QColor(p.text))
    pal.setColor(QPalette.Button, QColor(p.card))
    pal.setColor(QPalette.ButtonText, QColor(p.text))
    pal.setColor(QPalette.Highlight, QColor(p.selection))
    pal.setColor(QPalette.HighlightedText, QColor(p.selection_text))
    pal.setColor(QPalette.ToolTipBase, QColor(p.text))
    pal.setColor(QPalette.ToolTipText, QColor(p.bg))
    pal.setColor(QPalette.PlaceholderText, QColor(p.muted))
    app.setPalette(pal)
    app.setProperty("theme_mode", mode)
    app.setProperty("theme_effective", p.name)
    return p
