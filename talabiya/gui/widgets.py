"""Shared building blocks: cards, badges, buttons, money fields, message boxes."""
from __future__ import annotations

from collections.abc import Callable
from datetime import date

from PySide6.QtCore import QRegularExpression, Qt, Signal
from PySide6.QtGui import QPixmap, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from talabiya.core.money import CURRENCY, fmt, parse_qty, qty_text, to_millis
from talabiya.gui import icons, theme

WEEKDAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر",
          "نوفمبر", "ديسمبر"]


def weekday(d: date) -> str:
    return WEEKDAYS[d.weekday()]


def day_label(d: date) -> str:
    return f"{weekday(d)} {d.isoformat()}"


def money_text(millis: int) -> str:
    """'1,234.500 د.ل' with the number isolated so it never flips inside Arabic text."""
    return f"⁦{fmt(millis)}⁩ {CURRENCY}"


def repolish(w: QWidget) -> None:
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def label(text: str = "", role: str | None = None, *, wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    if role:
        lb.setProperty("role", role)
    lb.setWordWrap(wrap)
    return lb


def set_role(lb: QLabel, role: str) -> None:
    if lb.property("role") != role:
        lb.setProperty("role", role)
        repolish(lb)


def button(text: str, kind: str | None = None, icon: str | None = None, *, small: bool = False,
           on_click: Callable[[], object] | None = None, tip: str | None = None) -> QPushButton:
    b = QPushButton(text)
    if kind:
        b.setProperty("kind", kind)
    if small:
        b.setProperty("size", "sm")
    if icon:
        color = {"primary": "on_brand", "fresh": "on_green_strong", "danger": "on_danger"}.get(kind or "", "brand")
        b.setIcon(icons.icon(icon, theme.t(color), 18))
    if on_click:
        b.clicked.connect(lambda _=False: on_click())
    if tip:
        b.setToolTip(tip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def icon_button(name: str, tip: str, on_click: Callable[[], object], color: str = "ink_muted") -> QPushButton:
    b = QPushButton()
    b.setProperty("kind", "icon")
    b.setIcon(icons.icon(name, theme.t(color), 18))
    b.setToolTip(tip)
    b.setAccessibleName(tip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.clicked.connect(lambda _=False: on_click())
    return b


class Card(QFrame):
    def __init__(self, title: str | None = None, icon: str | None = None, note: str | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(20, 18, 20, 18)
        self.lay.setSpacing(12)
        self.header: QHBoxLayout | None = None
        if title:
            self.header = QHBoxLayout()
            self.header.setSpacing(8)
            if icon:
                ic = QLabel()
                ic.setPixmap(icons.pixmap(icon, theme.t("brand"), 20))
                self.header.addWidget(ic)
            self.header.addWidget(label(title, "h2"))
            self.header.addStretch(1)
            if note:
                self.header.addWidget(label(note, "muted"))
            self.lay.addLayout(self.header)


class Badge(QFrame):
    """Status pill: always an icon and a word (never colour alone)."""

    KINDS = {
        "new": ("surface_tint", "brand", "control_border"),
        "done": ("surface_fresh", "green_strong", None),
        "pending": ("surface_gold", "ink", None),
        "cancel": ("surface_alert", "danger", None),
        "gold": ("gold", "on_gold", None),
    }

    def __init__(self, kind: str, text: str, icon: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        bg, fg, border = self.KINDS[kind]
        b = f"border: 1px solid {theme.t(border)};" if border else "border: 0;"
        self.setStyleSheet(f"Badge {{ background: {theme.t(bg)}; border-radius: 14px; {b} }}"
                           f"QLabel {{ color: {theme.t(fg)}; font-weight: 700; font-size: 13px; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(6)
        if icon:
            ic = QLabel()
            ic.setPixmap(icons.pixmap(icon, theme.t(fg), 14, 2.6))
            lay.addWidget(ic)
        lay.addWidget(QLabel(text))
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


def state_badge(state: str) -> Badge:
    return {
        "empty": Badge("new", "لم يبدأ", "pause"),
        "open": Badge("pending", "قيد الشراء", "clock"),
        "done": Badge("done", "مكتمل", "check"),
    }[state]


def iso(text: str) -> str:
    """Isolate a Latin number / percent inside Arabic text so its sign and digits never flip."""
    return f"⁦{text}⁩"


def diff_badge(diff: int | None, open_text: str = "اليوم لم يُقفل") -> Badge:
    if diff is None:
        return Badge("pending", open_text, "clock")
    if diff == 0:
        return Badge("done", "مطابق", "check")
    if diff < 0:
        return Badge("cancel", f"عجز {iso(fmt(-diff))}", "alert")
    return Badge("pending", f"زيادة {iso(fmt(diff))}", "up")


class Alert(QFrame):
    STYLES = {"warn": ("surface_gold", "ink"), "bad": ("surface_alert", "danger"), "ok": ("surface_fresh", "green_strong"),
              "info": ("surface_tint", "brand")}

    def __init__(self, kind: str, icon: str, text: str, action: tuple[str, Callable[[], object]] | None = None) -> None:
        super().__init__()
        bg, fg = self.STYLES[kind]
        self.setStyleSheet(f"Alert {{ background: {theme.t(bg)}; border-radius: 14px; }}"
                           f"Alert > QLabel {{ color: {theme.t(fg)}; font-weight: 500; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon, theme.t(fg), 18))
        lay.addWidget(ic)
        lb = QLabel(text)
        lb.setWordWrap(True)
        lay.addWidget(lb, 1)
        if action:
            lay.addWidget(button(action[0], small=True, on_click=action[1]))


def logo(name: str, width: int) -> QLabel:
    lb = QLabel()
    pm = QPixmap(theme.asset(name))
    lb.setPixmap(pm.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation))
    lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lb


# --------------------------------------------------------------- number fields
MAX_INT_DIGITS = 7   # up to 9,999,999.999 — qty x price then stays far inside SQLite's 64-bit integers


class NumberEdit(QLineEdit):
    """Latin-digit decimal field (left-to-right) with up to ``decimals`` places."""

    valueChanged = Signal()

    def __init__(self, decimals: int = 3, placeholder: str = "0.000", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("num", True)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setPlaceholderText(placeholder)
        rx = QRegularExpression(rf"^\d{{0,{MAX_INT_DIGITS}}}([.,]\d{{0,{decimals}}})?$")
        self.setValidator(QRegularExpressionValidator(rx, self))
        self.textEdited.connect(lambda _t: self.valueChanged.emit())
        self.setInputMethodHints(Qt.InputMethodHint.ImhFormattedNumbersOnly)


class MoneyEdit(NumberEdit):
    def value(self) -> int:
        return to_millis(self.text().replace(",", "."))

    def set_value(self, millis: int, *, blank_zero: bool = True) -> None:
        self.setText("" if (millis == 0 and blank_zero) else fmt(millis).replace(",", ""))


class QtyEdit(NumberEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(3, "0", parent)

    def value(self):  # -> Decimal
        return parse_qty(self.text().replace(",", "."))

    def set_value(self, qty) -> None:  # qty: Decimal
        self.setText("" if not qty else qty_text(qty))


# --------------------------------------------------------------- messages
def _box(parent: QWidget | None, kind: QMessageBox.Icon, title: str, text: str) -> QMessageBox:
    box = QMessageBox(kind, title, text, parent=parent)
    box.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    return box


def info(parent: QWidget | None, text: str, title: str = "طلبية") -> None:
    _box(parent, QMessageBox.Icon.Information, title, text).exec()


def error(parent: QWidget | None, text: str, title: str = "تنبيه") -> None:
    _box(parent, QMessageBox.Icon.Warning, title, text).exec()


def confirm(parent: QWidget | None, text: str, yes: str = "نعم", no: str = "إلغاء", danger: bool = False) -> bool:
    box = _box(parent, QMessageBox.Icon.Warning if danger else QMessageBox.Icon.Question, "تأكيد", text)
    y = box.addButton(yes, QMessageBox.ButtonRole.AcceptRole)
    box.addButton(no, QMessageBox.ButtonRole.RejectRole)
    if danger:
        y.setProperty("kind", "danger")
    box.exec()
    return box.clickedButton() is y


def hline() -> QFrame:
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background: {theme.t('divider')};")
    return f


def clear_layout(lay) -> None:  # QLayout
    while lay.count():
        it = lay.takeAt(0)
        w = it.widget()
        if w is not None:
            w.deleteLater()
        elif it.layout() is not None:
            clear_layout(it.layout())
