"""Talabiya brand tokens (talabiya-brand/tokens.json) turned into a Qt style sheet."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication


def asset(name: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent))
    p = base / "talabiya" / "gui" / "assets" / name
    return str(p)


LIGHT = {
    "surface": "#ffffff", "surface_raised": "#ffffff", "surface_tint": "#f3f7fc", "surface_fresh": "#eaf6e7",
    "surface_alert": "#fdecea", "surface_gold": "#fff3cf", "ink": "#0a2a55", "ink_muted": "#44566f",
    "brand": "#063b78", "on_brand": "#ffffff", "green": "#3b9c2e", "green_strong": "#1f7a1c",
    "on_green_strong": "#ffffff", "gold": "#feb605", "on_gold": "#0a2a55", "tomato": "#dc2925",
    "danger": "#b3201c", "on_danger": "#ffffff", "divider": "#d5dfec", "control_border": "#6b7f9c",
    "page": "#f3f7fc",
}
DARK = {
    "surface": "#0a1830", "surface_raised": "#11264a", "surface_tint": "#0e2040", "surface_fresh": "#12301a",
    "surface_alert": "#3a1a1d", "surface_gold": "#3a2e0c", "ink": "#eef3fb", "ink_muted": "#a9b9d1",
    "brand": "#8fb8f0", "on_brand": "#07204a", "green": "#5fc455", "green_strong": "#6fd062",
    "on_green_strong": "#06210a", "gold": "#feb605", "on_gold": "#0a2a55", "tomato": "#ff6b64",
    "danger": "#ff8f8a", "on_danger": "#3a0705", "divider": "#1f3a64", "control_border": "#5f7798",
    "page": "#0a1830",
}

FONT_DISPLAY = "Cairo"
FONT_BODY = "Tajawal"
FONT_NUM = "Segoe UI"     # brand: Montserrat; not available offline -> Segoe UI (tabular Latin digits)

_current: dict[str, str] = dict(LIGHT)
_mode = "light"


def t(name: str) -> str:
    return _current[name]


def mode() -> str:
    return _mode


def load_fonts() -> None:
    for f in ("Cairo-Regular_0.ttf", "Cairo-ExtraBold.ttf", "Tajawal-Regular.ttf", "Tajawal-Medium.ttf",
              "Tajawal-Bold.ttf"):
        QFontDatabase.addApplicationFont(asset(f"fonts/{f}"))


def stylesheet(c: dict[str, str]) -> str:
    return f"""
* {{ font-family: "{FONT_BODY}"; font-size: 15px; color: {c['ink']}; }}
QMainWindow, QDialog, QWidget#page, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget
    {{ background: {c['page']}; }}
QWidget#sidebar {{ background: {c['surface_raised']}; border-left: 1px solid {c['divider']}; }}
QFrame#logoCard {{ background: #ffffff; border-radius: 14px; }}
QFrame#card {{ background: {c['surface_raised']}; border-radius: 22px; border: 1px solid {c['divider']}; }}
QFrame#tint {{ background: {c['surface_tint']}; border-radius: 14px; }}
QLabel {{ background: transparent; }}
QLabel[role="h1"] {{ font-family: "{FONT_DISPLAY}"; font-size: 26px; font-weight: 800; color: {c['brand']}; }}
QLabel[role="h2"] {{ font-family: "{FONT_DISPLAY}"; font-size: 18px; font-weight: 700; }}
QLabel[role="h3"] {{ font-family: "{FONT_DISPLAY}"; font-size: 22px; font-weight: 800; }}
QLabel[role="muted"] {{ color: {c['ink_muted']}; font-weight: 500; }}
QLabel[role="label"] {{ font-weight: 700; font-size: 14px; }}
QLabel[role="kpiLabel"] {{ color: {c['ink_muted']}; font-weight: 700; font-size: 14px; }}
QLabel[role="num"] {{ font-family: "{FONT_NUM}"; font-weight: 700; }}
QLabel[role="kpi"] {{ font-family: "{FONT_NUM}"; font-weight: 700; font-size: 28px; }}
QLabel[role="big"] {{ font-family: "{FONT_NUM}"; font-weight: 700; font-size: 30px; color: {c['brand']}; }}
QLabel[role="bigBad"] {{ font-family: "{FONT_NUM}"; font-weight: 700; font-size: 30px; color: {c['danger']}; }}
QLabel[role="bigOk"] {{ font-family: "{FONT_NUM}"; font-weight: 700; font-size: 30px; color: {c['green_strong']}; }}
QLabel[role="up"] {{ color: {c['danger']}; font-weight: 700; }}
QLabel[role="down"] {{ color: {c['green_strong']}; font-weight: 700; }}
QLabel[role="link"] {{ color: {c['brand']}; font-weight: 700; text-decoration: underline; }}

QPushButton {{ min-height: 44px; padding: 0 20px; border-radius: 14px; font-weight: 700; font-size: 15px;
    border: 2px solid {c['control_border']}; background: {c['surface_raised']}; color: {c['brand']}; }}
QPushButton:hover {{ background: {c['surface_tint']}; }}
QPushButton:focus {{ outline: none; border-color: {c['brand']}; }}
QPushButton[kind="primary"] {{ background: {c['brand']}; color: {c['on_brand']}; border-color: {c['brand']}; }}
QPushButton[kind="primary"]:hover {{ background: {c['ink']}; border-color: {c['ink']}; }}
QPushButton[kind="fresh"] {{ background: {c['green_strong']}; color: {c['on_green_strong']};
    border-color: {c['green_strong']}; }}
QPushButton[kind="danger"] {{ background: {c['danger']}; color: {c['on_danger']}; border-color: {c['danger']}; }}
QPushButton[size="sm"] {{ min-height: 34px; padding: 0 12px; font-size: 13px; border-radius: 10px; }}
QPushButton[kind="icon"] {{ min-height: 36px; min-width: 36px; max-width: 36px; padding: 0; border: 0;
    background: transparent; border-radius: 10px; }}
QPushButton[kind="icon"]:hover {{ background: {c['surface_alert']}; }}
QPushButton[kind="link"] {{ border: 0; background: transparent; color: {c['brand']}; text-decoration: underline;
    min-height: 28px; padding: 0; }}
QPushButton:disabled {{ background: {c['surface_tint']}; color: {c['ink_muted']}; border-color: {c['divider']}; }}

QPushButton[nav="true"] {{ text-align: right; border: 0; background: transparent; color: {c['ink']};
    padding: 0 12px; min-height: 44px; }}
QPushButton[nav="true"]:hover {{ background: {c['surface_tint']}; }}
QPushButton[nav="true"]:checked {{ background: {c['brand']}; color: {c['on_brand']}; }}

QLineEdit, QComboBox, QDateEdit, QPlainTextEdit {{ min-height: 40px; padding: 0 10px;
    border: 2px solid {c['control_border']}; border-radius: 10px; background: {c['surface_raised']};
    color: {c['ink']}; selection-background-color: {c['brand']}; selection-color: {c['on_brand']}; }}
QPlainTextEdit {{ padding: 6px 10px; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QPlainTextEdit:focus {{ border-color: {c['brand']}; }}
QLineEdit[num="true"] {{ font-family: "{FONT_NUM}"; font-weight: 700; }}
QLineEdit[manual="true"] {{ background: {c['surface_gold']}; }}
QLineEdit[error="true"] {{ border-color: {c['danger']}; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: 0; width: 26px; }}
QComboBox QAbstractItemView {{ background: {c['surface_raised']}; border: 1px solid {c['control_border']};
    selection-background-color: {c['surface_tint']}; selection-color: {c['ink']}; }}
QCalendarWidget QWidget {{ background: {c['surface_raised']}; }}
QCalendarWidget QToolButton {{ color: {c['brand']}; font-weight: 700; background: transparent; }}

QTabBar::tab {{ min-height: 40px; padding: 0 16px; margin-left: 8px; border: 2px solid {c['control_border']};
    border-radius: 14px; background: {c['surface_raised']}; font-weight: 700; }}
QTabBar::tab:selected {{ background: {c['brand']}; color: {c['on_brand']}; border-color: {c['brand']}; }}

QTableWidget {{ background: {c['surface_raised']}; border: 0; gridline-color: {c['divider']};
    alternate-background-color: {c['surface_tint']}; selection-background-color: {c['surface_tint']};
    selection-color: {c['ink']}; }}
QTableWidget::item {{ padding: 4px 6px; border-bottom: 1px solid {c['divider']}; }}
QHeaderView::section {{ background: {c['surface_raised']}; color: {c['ink_muted']}; font-weight: 700;
    font-size: 13px; border: 0; border-bottom: 2px solid {c['divider']}; padding: 8px 6px; }}
QListWidget, QTreeWidget {{ background: {c['surface_raised']}; border: 1px solid {c['divider']}; border-radius: 14px;
    padding: 6px; }}
QTreeWidget::item, QListWidget::item {{ min-height: 30px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['control_border']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {c['control_border']}; border-radius: 4px; min-width: 30px; }}
QToolTip {{ background: {c['ink']}; color: {c['surface']}; border: 0; padding: 6px; }}
QMessageBox QLabel {{ min-width: 300px; }}
QCheckBox {{ spacing: 8px; }}
"""


def apply(app: QApplication, name: str) -> None:
    global _mode
    _mode = "dark" if name == "dark" else "light"
    _current.clear()
    _current.update(DARK if _mode == "dark" else LIGHT)
    pal = app.palette()
    pal.setColor(QPalette.ColorRole.Window, QColor(t("page")))
    pal.setColor(QPalette.ColorRole.Base, QColor(t("surface_raised")))
    pal.setColor(QPalette.ColorRole.Text, QColor(t("ink")))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(t("ink")))
    pal.setColor(QPalette.ColorRole.Button, QColor(t("surface_raised")))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(t("brand")))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(t("brand")))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(t("on_brand")))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(t("ink_muted")))
    app.setPalette(pal)
    app.setStyleSheet(stylesheet(_current))
