"""Shared application state: the open database, the selected day, navigation."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, QObject, Qt, Signal
from PySide6.QtWidgets import QDateEdit, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from talabiya.core.repo import Repo
from talabiya.gui import icons, theme
from talabiya.gui import widgets as W


class AppState(QObject):
    dayChanged = Signal()
    dataChanged = Signal()
    navigate = Signal(str)

    def __init__(self, repo: Repo, db_path: Path) -> None:
        super().__init__()
        self.repo = repo
        self.db_path = db_path
        self.day = date.today()
        self.restaurant_id: int | None = None   # selected tab on the purchases page

    @property
    def day_iso(self) -> str:
        return self.day.isoformat()

    def set_day(self, d: date) -> None:
        if d != self.day:
            self.day = d
            self.dayChanged.emit()

    def go(self, page: str, *, day: date | None = None, restaurant_id: int | None = None) -> None:
        if restaurant_id is not None:
            self.restaurant_id = restaurant_id
        if day is not None:
            self.set_day(day)
        self.navigate.emit(page)


class DatePill(QWidget):
    """Weekday + calendar date picker bound to the shared day."""

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(icons.pixmap("calendar", theme.t("brand"), 20))
        lay.addWidget(ic)
        self.wd = W.label("", "label")
        lay.addWidget(self.wd)
        self.edit = QDateEdit()
        self.edit.setCalendarPopup(True)
        self.edit.setDisplayFormat("yyyy-MM-dd")
        self.edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.edit.setMinimumWidth(150)
        self.edit.setProperty("num", True)
        lay.addWidget(self.edit)
        today = W.button("اليوم", small=True, on_click=lambda: state.set_day(date.today()))
        lay.addWidget(today)
        self.edit.dateChanged.connect(self._picked)
        state.dayChanged.connect(self.sync)
        self.sync()

    def _picked(self, qd: QDate) -> None:
        self.state.set_day(date(qd.year(), qd.month(), qd.day()))

    def sync(self) -> None:
        d = self.state.day
        self.edit.blockSignals(True)
        self.edit.setDate(QDate(d.year, d.month, d.day))
        self.edit.blockSignals(False)
        self.wd.setText(W.weekday(d))


class Page(QWidget):
    """A screen with a title row; subclasses fill ``self.body`` and implement ``refresh``."""

    title = ""
    subtitle = ""
    uses_day = False

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.setObjectName("page")
        self.state = state
        self.repo = state.repo
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 22)
        outer.setSpacing(18)
        top = QHBoxLayout()
        top.setSpacing(16)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(W.label(self.title, "h1"))
        self.sub_lb = W.label(self.subtitle, "muted")
        titles.addWidget(self.sub_lb)
        top.addLayout(titles)
        top.addStretch(1)
        self.top_actions = QHBoxLayout()
        self.top_actions.setSpacing(10)
        top.addLayout(self.top_actions)
        if self.uses_day:
            top.addWidget(DatePill(state))
        outer.addLayout(top)
        self.body = QVBoxLayout()
        self.body.setSpacing(18)
        outer.addLayout(self.body, 1)

    def refresh(self) -> None:  # pragma: no cover - overridden
        pass

    def leave(self) -> bool:
        """Called before navigating away. Return False to stay."""
        return True
