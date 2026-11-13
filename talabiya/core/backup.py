"""Scheduled backups of the database into a folder the user chooses.

Frequency: daily / weekly / monthly / off. A backup is due when the last one is at least that old.
Backups are consistent copies made with SQLite's online-backup API; the newest ``KEEP`` are kept.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from talabiya.core.db import check_db
from talabiya.core.repo import Repo, RepoError

FREQUENCIES = {"daily": "يومي", "weekly": "أسبوعي", "monthly": "شهري", "off": "متوقف"}
_PERIOD = {"daily": timedelta(days=1), "weekly": timedelta(days=7), "monthly": timedelta(days=30)}
PREFIX = "talabiya_"
KEEP = 60
STAMP = "%Y%m%d_%H%M%S"


def frequency(repo: Repo) -> str:
    f = repo.get_setting("backup_frequency", "daily") or "daily"
    return f if f in FREQUENCIES else "daily"


def folder(repo: Repo) -> Path | None:
    v = repo.get_setting("backup_folder")
    return Path(v) if v else None


def last_backup(repo: Repo) -> datetime | None:
    v = repo.get_setting("last_backup")
    try:
        return datetime.fromisoformat(v) if v else None
    except ValueError:
        return None


def is_due(freq: str, last: datetime | None, now: datetime) -> bool:
    if freq == "off":
        return False
    if last is None:
        return True
    return now - last >= _PERIOD[freq] - timedelta(minutes=1)


def _copy_db(src: sqlite3.Connection, target: Path) -> None:
    """Consistent copy of ``src`` into ``target`` through a temporary file, so ``target`` is never half-written."""
    tmp = target.with_name(target.name + ".tmp")
    try:
        tmp.unlink(missing_ok=True)
        out = sqlite3.connect(str(tmp))
        try:
            src.backup(out)
        finally:
            out.close()
        os.replace(tmp, target)
    except BaseException:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def make_backup(repo: Repo, dest: Path, now: datetime | None = None) -> Path:
    now = now or datetime.now()
    target = dest / f"{PREFIX}{now.strftime(STAMP)}.db"
    try:
        dest.mkdir(parents=True, exist_ok=True)
        _copy_db(repo.conn, target)
    except (OSError, sqlite3.Error) as e:
        raise RepoError(f"تعذر حفظ النسخة الاحتياطية في: {dest}\n({e})") from e
    repo.set_setting("last_backup", now.isoformat(timespec="seconds"))   # only after a complete copy
    prune(dest)
    return target


def run_if_due(repo: Repo, now: datetime | None = None) -> Path | None:
    """Make a backup when one is due and a folder is set. Returns the file, or None."""
    now = now or datetime.now()
    dest = folder(repo)
    if dest is None or not is_due(frequency(repo), last_backup(repo), now):
        return None
    return make_backup(repo, dest, now)


def list_backups(dest: Path) -> list[Path]:
    if not dest.is_dir():
        return []
    return sorted(dest.glob(f"{PREFIX}*.db"), reverse=True)


def prune(dest: Path, keep: int = KEEP) -> None:
    for old in list_backups(dest)[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def restore(source: Path, db_path: Path) -> None:
    """Replace the database file with ``source``. The caller must have closed its connection.

    ``source`` is first copied to a staging file and checked there, so it may be any file — even
    ``<name>.before-restore.db`` itself. The current file is then kept as ``<name>.before-restore.db``
    and the staged copy is moved into place in one step. On any error the current file is untouched.
    """
    try:
        if source.resolve() == db_path.resolve():
            raise RepoError("هذا هو ملف البيانات الحالي نفسه. اختر ملف نسخة احتياطية")
    except OSError as e:
        raise RepoError(f"تعذر قراءة الملف المختار: {e}") from e
    reason = check_db(source)
    if reason:
        raise RepoError(reason)
    staged = db_path.with_name(db_path.name + ".restore.tmp")
    try:
        src = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            _copy_db(src, staged)
        finally:
            src.close()
        reason = check_db(staged)
        if reason:
            raise RepoError(reason)
        if db_path.exists():
            shutil.copy2(db_path, db_path.with_suffix(".before-restore.db"))
        os.replace(staged, db_path)
    except (OSError, sqlite3.Error) as e:
        raise RepoError(f"تعذر استرجاع النسخة، وبقيت البيانات الحالية كما هي.\n({e})") from e
    finally:
        try:
            staged.unlink(missing_ok=True)
        except OSError:
            pass
