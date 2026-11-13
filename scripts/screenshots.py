"""Render every page (demo data, temporary database) to PNG files for review.

    python scripts/screenshots.py <out-dir> [light|dark]
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QLocale, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    mode = sys.argv[2] if len(sys.argv) > 2 else "light"
    tmp = Path(tempfile.mkdtemp())
    os.environ["TALABIYA_HOME"] = str(tmp)
    from scripts.demo_data import fill
    from talabiya.core.db import connect
    from talabiya.core.repo import Repo
    from talabiya.gui import qt_ar, theme
    from talabiya.gui.auth_dialogs import LoginDialog, SetupDialog
    from talabiya.gui.main_window import NAV, MainWindow
    from talabiya.gui.state import AppState

    app = QApplication([])
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    QLocale.setDefault(QLocale("ar_LY"))
    theme.load_fonts()
    qt_ar.install("ar")
    theme.apply(app, mode)

    empty = tmp / "empty.db"
    rep0 = Repo(connect(empty))
    s = SetupDialog(rep0)
    s.show()
    app.processEvents()
    s.grab().save(str(out / f"00-setup-{mode}.png"))
    s.stack.setCurrentIndex(1)
    s._sync()
    app.processEvents()
    s.grab().save(str(out / f"00b-setup-catalog-{mode}.png"))
    s.close()
    win0 = MainWindow(AppState(rep0, empty), lambda _m: None, lambda: None)
    win0.resize(1366, 860)
    win0.show()
    win0.show_page("dash")
    app.processEvents()
    win0.grab().save(str(out / f"01-empty-{mode}.png"))
    win0.hide()

    db = tmp / "demo.db"
    fill(db, date.today())
    repo = Repo(connect(db))
    lg = LoginDialog(repo)
    lg.show()
    app.processEvents()
    lg.grab().save(str(out / f"02-login-{mode}.png"))
    lg.close()
    st = AppState(repo, db)
    win = MainWindow(st, lambda _m: None, lambda: None)
    win.resize(1366, 860)
    win.show()
    for i, (key, *_rest) in enumerate(NAV, 3):
        win.show_page(key)
        app.processEvents()
        page = win.pages[key]
        page.resize(page.sizeHint())
        app.processEvents()
        win.grab().save(str(out / f"{i:02d}-{key}-{mode}.png"))
        # full page (scrolled content) too
        page.grab().save(str(out / f"{i:02d}-{key}-full-{mode}.png"))
    print("saved to", out)


if __name__ == "__main__":
    main()
