"""Regression tests for the findings of the first external review (Codex, 2026-11-13)."""
from __future__ import annotations

import os
import sqlite3
import stat
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from talabiya.core import auth, backup
from talabiya.core.db import SCHEMA_VERSION, connect, is_talabiya_db, migrate
from talabiya.core.models import Line, Sheet
from talabiya.core.repo import Repo, RepoError


def _db_with(path, restaurant: str) -> None:
    conn = connect(path)
    Repo(conn).add_restaurant(restaurant)
    conn.close()


def _names(path) -> list[str]:
    conn = connect(path)
    try:
        return [r.name for r in Repo(conn).restaurants(include_inactive=True)]
    finally:
        conn.close()


# ------------------------------------------------------------------ 1-3 restore
def test_restore_from_before_restore_file_keeps_its_content(tmp_path):
    db = tmp_path / "talabiya.db"
    safety = db.with_suffix(".before-restore.db")
    _db_with(safety, "OLD")
    _db_with(db, "R")
    backup.restore(safety, db)
    assert _names(db) == ["OLD"]
    assert _names(safety) == ["R"]          # the replaced data is the new safety copy


def test_restore_refuses_the_current_file_and_leaves_it_alone(tmp_path):
    db = tmp_path / "talabiya.db"
    _db_with(db, "R")
    with pytest.raises(RepoError):
        backup.restore(db, db)
    assert _names(db) == ["R"]


def test_restore_refuses_wrong_columns(tmp_path):
    bad = tmp_path / "bad.db"
    conn = sqlite3.connect(bad)
    for t in ("restaurants", "units", "items", "day_sheets", "purchase_lines", "day_close", "settings"):
        conn.execute(f"CREATE TABLE {t}(wrong TEXT)")
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.close()
    assert not is_talabiya_db(bad)
    db = tmp_path / "talabiya.db"
    _db_with(db, "R")
    with pytest.raises(RepoError):
        backup.restore(bad, db)
    assert _names(db) == ["R"]


def test_restore_refuses_a_damaged_file(tmp_path):
    good = tmp_path / "good.db"
    conn = connect(good)
    repo = Repo(conn)
    rid = repo.add_restaurant("R")
    lines = [Line(f"صنف {i}" * 20, Decimal(1), "كجم", 1000) for i in range(400)]
    repo.save_sheet(Sheet("2026-11-01", rid, received=1_000_000, lines=lines))
    conn.close()
    raw = bytearray(good.read_bytes())
    page = 4096
    for off in range(page * 3, min(len(raw), page * 8)):   # scribble over data pages, keep the header
        raw[off] = 0xFF
    bad = tmp_path / "bad.db"
    bad.write_bytes(bytes(raw))
    assert not is_talabiya_db(bad)


def test_restore_rejects_a_non_database(tmp_path):
    txt = tmp_path / "notes.db"
    txt.write_text("hello", encoding="utf-8")
    db = tmp_path / "talabiya.db"
    _db_with(db, "R")
    with pytest.raises(RepoError):
        backup.restore(txt, db)
    assert _names(db) == ["R"]


# ------------------------------------------------------------------ 7 backup errors
def test_backup_write_error_is_a_repo_error_and_keeps_last_backup(repo, tmp_path):
    dest = tmp_path / "bk"
    dest.mkdir()
    now = datetime(2026, 11, 13, 9, 0, 0)
    target = dest / f"{backup.PREFIX}{now.strftime(backup.STAMP)}.db"
    target.mkdir()                      # a folder where the file should go: the copy cannot land
    with pytest.raises(RepoError):
        backup.make_backup(repo, dest, now)
    assert backup.last_backup(repo) is None
    assert not list(dest.glob("*.tmp"))


def test_backup_into_read_only_file_is_a_repo_error(repo, tmp_path):
    dest = tmp_path / "bk"
    dest.mkdir()
    now = datetime(2026, 11, 13, 9, 0, 0)
    target = dest / f"{backup.PREFIX}{now.strftime(backup.STAMP)}.db"
    target.write_bytes(b"")
    os.chmod(target, stat.S_IREAD)
    try:
        with pytest.raises(RepoError):
            backup.make_backup(repo, dest, now)
    finally:
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
    assert backup.last_backup(repo) is None


def test_prune_keeps_the_newest_60(repo, tmp_path):
    dest = tmp_path / "bk"
    start = datetime(2026, 1, 1)
    for i in range(61):
        backup.make_backup(repo, dest, start + timedelta(days=i))
    files = backup.list_backups(dest)
    assert len(files) == 60
    assert files[-1].name == f"{backup.PREFIX}{(start + timedelta(days=1)).strftime(backup.STAMP)}.db"


# ------------------------------------------------------------------ 8 atomic migration
def test_failed_migration_leaves_nothing_behind(tmp_path):
    path = tmp_path / "half.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE units(x)")     # makes the v1 script fail after creating `restaurants`
    conn.commit()
    with pytest.raises(sqlite3.Error):
        migrate(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {"units"}
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
    conn.close()


def test_new_database_reaches_current_version(tmp_path):
    conn = connect(tmp_path / "n.db")
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    conn.close()


# ------------------------------------------------------------------ 6 amount limits
def test_huge_amount_is_refused_before_sql(repo):
    rid = repo.add_restaurant("R")
    day = "2026-11-13"
    repo.save_sheet(Sheet(day, rid, received=100_000))
    big = Line("دقيق", Decimal("999999999.999"), "كجم", 999_999_999_999)
    with pytest.raises(RepoError):
        repo.save_sheet(Sheet(day, rid, received=100_000, lines=[big]))
    assert repo.sheet(day, rid).received == 100_000
    assert repo.sheet(day, rid).lines == []


def test_manual_total_zero_survives_reload(repo):
    rid = repo.add_restaurant("R")
    day = "2026-11-13"
    repo.save_sheet(Sheet(day, rid, received=5_000,
                          lines=[Line("علب", Decimal(600), "قطعة", 1_000, total_override=0)]))
    ln = repo.sheet(day, rid).lines[0]
    assert ln.total_override == 0 and ln.total == 0


# ------------------------------------------------------------------ GUI: 4, 5, 9
@pytest.fixture
def window(qtbot, tmp_path):
    from talabiya.gui.main_window import MainWindow
    from talabiya.gui.state import AppState

    db = tmp_path / "g.db"
    conn = connect(db)
    repo = Repo(conn)
    win = MainWindow(AppState(repo, db), lambda _m: None, lambda: None)
    qtbot.addWidget(win)
    win.show()
    yield win, repo
    conn.close()


def test_close_draft_is_kept_when_the_day_changes(window):
    win, repo = window
    repo.add_restaurant("R")
    win.state.set_day(date(2026, 11, 14))
    win.show_page("close")
    page = win.pages["close"]
    page.actual.setText("55.000")
    page.notes.setPlainText("draft")
    win.state.set_day(date(2026, 11, 15))
    dc = repo.day_close("2026-11-14")
    assert dc.actual_cash == 55_000 and dc.notes == "draft"
    assert repo.day_close("2026-11-15").actual_cash is None


def test_close_draft_is_not_written_again_after_the_day_is_deleted(window):
    win, repo = window
    repo.add_restaurant("R")
    win.state.set_day(date(2026, 11, 14))
    win.show_page("close")
    win.pages["close"].actual.setText("55.000")
    win.show_page("history")                 # saves the draft
    repo.delete_day("2026-11-14")
    win.show_page("close")
    assert repo.day_close("2026-11-14").actual_cash is None


def test_deleting_the_last_restaurant_after_the_close_page(window):
    win, repo = window
    rid = repo.add_restaurant("R")
    win.show_page("close")
    win.show_page("rests")
    repo.delete_restaurant(rid)
    win.show_page("close")                  # empty state
    from PySide6.QtCore import QCoreApplication, QEvent

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)   # really destroy the old fields
    win.show_page("dash")                 # leaving must not touch deleted fields
    win.flush()


def test_enter_does_not_bypass_the_login_wait(qtbot, repo):
    from talabiya.gui.auth_dialogs import LoginDialog

    auth.setup(repo, "1234", "س", "ج")
    dlg = LoginDialog(repo)
    qtbot.addWidget(dlg)
    for _ in range(3):
        dlg.pw.setText("bad")
        dlg._login()
    assert dlg.fails == 3
    dlg.pw.setText("1234")
    dlg.pw.returnPressed.emit()             # Enter during the wait
    assert dlg.fails == 3 and dlg.result() == 0
