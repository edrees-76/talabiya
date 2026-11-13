"""Main window: sidebar navigation + stacked pages."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from talabiya import __version__
from talabiya.gui import icons, theme
from talabiya.gui import widgets as W
from talabiya.gui.pages.close_page import ClosePage
from talabiya.gui.pages.dashboard import DashboardPage
from talabiya.gui.pages.day_page import DayPage
from talabiya.gui.pages.history_page import HistoryPage
from talabiya.gui.pages.items_page import ItemsPage
from talabiya.gui.pages.restaurants_page import RestaurantsPage
from talabiya.gui.pages.settings_page import SettingsPage
from talabiya.gui.state import AppState, Page

NAV = [
    ("dash", "لوحة القيادة", "home", DashboardPage, "Ctrl+1"),
    ("day", "مشتريات اليوم", "cart", DayPage, "Ctrl+2"),
    ("close", "إقفال اليوم", "scale", ClosePage, "Ctrl+3"),
    ("history", "السجل", "clock", HistoryPage, "Ctrl+4"),
    ("rests", "المطاعم", "store", RestaurantsPage, "Ctrl+5"),
    ("items", "الأصناف والوحدات", "list", ItemsPage, "Ctrl+6"),
    ("settings", "الإعدادات", "gear", SettingsPage, "Ctrl+7"),
]


class MainWindow(QMainWindow):
    def __init__(self, state: AppState, on_theme, on_logout) -> None:  # callables
        super().__init__()
        self.state = state
        self._on_theme = on_theme
        self._on_logout = on_logout
        self.setWindowTitle("مشتريات المطاعم")
        self.setWindowIcon(QIcon(theme.asset("talabiya.ico")))
        self.resize(1366, 860)
        self.setMinimumSize(1100, 680)
        self.pages: dict[str, Page] = {}
        self.current = ""

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(250)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(16, 16, 16, 16)
        sl.setSpacing(4)
        lc = QFrame()
        lc.setObjectName("logoCard")
        ll = QVBoxLayout(lc)
        ll.setContentsMargins(6, 6, 6, 6)
        ll.addWidget(W.logo("logo-horizontal.jpg", 200))
        sl.addWidget(lc)
        sl.addSpacing(12)

        self.stack = QStackedWidget()
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.nav_buttons: dict[str, QPushButton] = {}
        for key, text, ic, cls, sc in NAV:
            b = QPushButton(text)
            b.setProperty("nav", True)
            b.setCheckable(True)
            b.setIcon(icons.icon(ic, theme.t("ink"), 20, active_color=theme.t("on_brand")))
            b.setToolTip(f"{text} ({sc})")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.show_page(k))
            self.group.addButton(b)
            sl.addWidget(b)
            self.nav_buttons[key] = b
            page = cls(state)
            self.pages[key] = page
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
            QShortcut(QKeySequence(sc), self, activated=lambda k=key: self.show_page(k))
        sl.addStretch(1)
        dark = theme.mode() == "dark"
        tb = QPushButton("الوضع الفاتح" if dark else "الوضع الداكن")
        tb.setProperty("nav", True)
        tb.setIcon(icons.icon("sun" if dark else "moon", theme.t("ink"), 20))
        tb.clicked.connect(lambda: self._on_theme("light" if dark else "dark"))
        sl.addWidget(tb)
        lo = QPushButton("قفل البرنامج")
        lo.setProperty("nav", True)
        lo.setIcon(icons.icon("lock", theme.t("ink"), 20))
        lo.setToolTip("يغلق الشاشة ويطلب كلمة السر (Ctrl+L)")
        lo.clicked.connect(self._logout)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self._logout)
        sl.addWidget(lo)
        sl.addWidget(W.label(f"الإصدار {__version__}", "muted"), 0, Qt.AlignmentFlag.AlignHCenter)

        root.addWidget(side)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        state.navigate.connect(self.show_page)
        state.dayChanged.connect(self._refresh_current)
        state.dataChanged.connect(self._mark_stale)
        self._stale: set[str] = set()

    def show_page(self, key: str) -> None:
        if key == self.current:
            self.pages[key].refresh()
            return
        if self.current and not self.pages[self.current].leave():
            self.nav_buttons[self.current].setChecked(True)
            return
        self.current = key
        self.nav_buttons[key].setChecked(True)
        self.stack.setCurrentIndex([k for k, *_ in NAV].index(key))
        self.pages[key].refresh()
        self._stale.discard(key)

    def _refresh_current(self) -> None:
        if self.current:
            self.pages[self.current].refresh()

    def _mark_stale(self) -> None:
        self._stale = set(self.pages) - {self.current}

    def _logout(self) -> None:
        if self.current and not self.pages[self.current].leave():
            return
        self._on_logout()

    def flush(self) -> None:
        if self.current:
            self.pages[self.current].leave()

    def closeEvent(self, e: QCloseEvent) -> None:  # noqa: N802
        self.flush()
        super().closeEvent(e)
        QApplication.instance().quit()
