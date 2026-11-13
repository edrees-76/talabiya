"""Program entry: setup or login, main window, theme switch, lock, restore, backups on start and exit."""
from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QLocale, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog

from talabiya import APP_NAME, APP_TITLE
from talabiya.core import auth, backup
from talabiya.core.db import connect, default_db_path
from talabiya.core.repo import Repo, RepoError
from talabiya.gui import qt_ar, theme
from talabiya.gui import widgets as W
from talabiya.gui.auth_dialogs import LoginDialog, SetupDialog
from talabiya.gui.main_window import MainWindow
from talabiya.gui.state import AppState


class Controller:
    def __init__(self, app: QApplication, db_path: Path) -> None:
        self.app = app
        self.db_path = db_path
        self.conn = connect(db_path)
        self.repo = Repo(self.conn)
        self.window: MainWindow | None = None
        self.state: AppState | None = None
        theme.apply(app, self.repo.get_setting("theme", "light") or "light")

    # ------------------------------------------------------------ start
    def start(self) -> bool:
        if not auth.is_configured(self.repo):
            if SetupDialog(self.repo).exec() != QDialog.DialogCode.Accepted:
                return False
        elif LoginDialog(self.repo).exec() != QDialog.DialogCode.Accepted:
            return False
        self._backup_quietly()
        self._build()
        return True

    def _build(self, page: str = "dash") -> None:
        old = self.window
        day = self.state.day if self.state else None
        rid = self.state.restaurant_id if self.state else None
        self.state = AppState(self.repo, self.db_path)
        if day:
            self.state.day = day
        self.state.restaurant_id = rid
        self.window = MainWindow(self.state, self.set_theme, self.lock)
        self.window.pages["settings"].restore_handler = self.restore  # type: ignore[attr-defined]
        if old is not None:
            self.window.setGeometry(old.geometry())
            if old.isMaximized():
                self.window.showMaximized()
            old.hide()
            old.deleteLater()
            self.window.show()
        else:
            self.window.showMaximized()
        self.window.show_page(page)

    # ------------------------------------------------------------ actions
    def set_theme(self, name: str) -> None:
        if self.window:
            self.window.flush()
        self.repo.set_setting("theme", name)
        theme.apply(self.app, name)
        self._build(self.window.current if self.window else "dash")

    def lock(self) -> None:
        if not self.window:
            return
        self.window.hide()
        if LoginDialog(self.repo).exec() == QDialog.DialogCode.Accepted:
            self.window.show()
            self.window.show_page(self.window.current or "dash")
        else:
            self.app.quit()

    def restore(self, source: Path) -> None:
        if self.window:
            self.window.flush()
        self.conn.close()
        try:
            backup.restore(source, self.db_path)
        except RepoError as e:
            W.error(self.window, str(e))
        finally:
            self.conn = connect(self.db_path)
            self.repo = Repo(self.conn)
        W.info(self.window, "تم استرجاع النسخة. سيُطلب منك الدخول بكلمة سر تلك النسخة")
        if self.window:
            self.window.hide()
        if not auth.is_configured(self.repo):
            ok = SetupDialog(self.repo).exec() == QDialog.DialogCode.Accepted
        else:
            ok = LoginDialog(self.repo).exec() == QDialog.DialogCode.Accepted
        if not ok:
            self.app.quit()
            return
        self._build("settings")

    def _backup_quietly(self) -> None:
        try:
            backup.run_if_due(self.repo)
        except (RepoError, OSError) as e:
            W.error(None, f"تعذر أخذ النسخة الاحتياطية التلقائية: {e}\nاختر مجلداً آخر من الإعدادات.")

    def shutdown(self) -> None:
        if self.window:
            self.window.flush()
        self._backup_quietly()
        self.conn.close()


def _log_path() -> Path:
    return default_db_path().parent / "error.log"


def _excepthook(exc_type, exc, tb) -> None:
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    try:
        p = _log_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.now().isoformat(timespec='seconds')}\n{text}")
    except OSError:
        pass
    sys.__stderr__.write(text) if sys.__stderr__ else None
    if QApplication.instance():
        W.error(None, f"حدث خطأ غير متوقع. بياناتك المحفوظة سليمة.\nسُجّل الخطأ في:\n{_log_path()}\n\n{exc}")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_TITLE)
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    QLocale.setDefault(QLocale("ar_LY"))
    app.setWindowIcon(QIcon(theme.asset("talabiya.ico")))
    theme.load_fonts()
    qt_ar.install("ar")
    sys.excepthook = _excepthook
    try:
        ctl = Controller(app, default_db_path())
    except RuntimeError as e:
        W.error(None, str(e))
        return 1
    if not ctl.start():
        ctl.conn.close()
        return 0
    app.aboutToQuit.connect(ctl.shutdown)
    return app.exec()
