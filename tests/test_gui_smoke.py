"""Every page builds and refreshes on an empty and on a filled database."""
from datetime import date

import pytest

from scripts.demo_data import fill
from talabiya.core.db import connect
from talabiya.core.repo import Repo
from talabiya.gui import theme
from talabiya.gui.main_window import NAV, MainWindow
from talabiya.gui.state import AppState


@pytest.mark.parametrize("filled", [False, True])
def test_all_pages(qtbot, tmp_path, filled):
    theme.apply(qtbot_app(), "light")
    db = tmp_path / "t.db"
    if filled:
        fill(db, date.today())
    repo = Repo(connect(db))
    win = MainWindow(AppState(repo, db), lambda _m: None, lambda: None)
    qtbot.addWidget(win)
    win.show()
    for key, *_ in NAV:
        win.show_page(key)
        assert win.current == key
    win.flush()


def qtbot_app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance()
