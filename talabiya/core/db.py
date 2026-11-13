"""SQLite connection and schema (migrations keyed on PRAGMA user_version)."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from talabiya import APP_NAME

DB_FILENAME = "talabiya.db"

_SCHEMA_V1 = """
CREATE TABLE restaurants(
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE COLLATE NOCASE,
    note    TEXT NOT NULL DEFAULT '',
    active  INTEGER NOT NULL DEFAULT 1,
    sort    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE units(
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE,
    sort  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE items(
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    default_unit  TEXT NOT NULL DEFAULT '',
    active        INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE day_sheets(
    id             INTEGER PRIMARY KEY,
    day            TEXT NOT NULL,                 -- YYYY-MM-DD
    restaurant_id  INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE RESTRICT,
    received       INTEGER NOT NULL DEFAULT 0,    -- milli-dinars
    wage           INTEGER NOT NULL DEFAULT 0,
    entry_fee      INTEGER NOT NULL DEFAULT 0,
    notes          TEXT NOT NULL DEFAULT '',
    done           INTEGER NOT NULL DEFAULT 0,
    UNIQUE(day, restaurant_id)
);
CREATE TABLE purchase_lines(
    id               INTEGER PRIMARY KEY,
    sheet_id         INTEGER NOT NULL REFERENCES day_sheets(id) ON DELETE CASCADE,
    seq              INTEGER NOT NULL,
    item             TEXT NOT NULL,
    qty              TEXT NOT NULL DEFAULT '0',   -- decimal string
    unit             TEXT NOT NULL DEFAULT '',
    unit_price       INTEGER NOT NULL DEFAULT 0,  -- milli-dinars
    total            INTEGER NOT NULL DEFAULT 0,  -- milli-dinars
    total_manual     INTEGER NOT NULL DEFAULT 0,  -- 1 = total typed by hand, not qty x price
    note             TEXT NOT NULL DEFAULT ''
);
CREATE INDEX ix_lines_sheet ON purchase_lines(sheet_id, seq);
CREATE INDEX ix_lines_item ON purchase_lines(item);
CREATE INDEX ix_sheets_day ON day_sheets(day);
CREATE TABLE day_close(
    day          TEXT PRIMARY KEY,
    actual_cash  INTEGER,                         -- NULL until entered
    notes        TEXT NOT NULL DEFAULT '',
    closed       INTEGER NOT NULL DEFAULT 0,
    closed_at    TEXT
);
CREATE TABLE settings(
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
"""

MIGRATIONS: list[str] = [_SCHEMA_V1]
SCHEMA_VERSION = len(MIGRATIONS)
REQUIRED_TABLES = {"restaurants", "units", "items", "day_sheets", "purchase_lines", "day_close", "settings"}


def default_db_path() -> Path:
    base = os.environ.get("TALABIYA_HOME") or os.path.join(os.environ.get("APPDATA", str(Path.home())), APP_NAME)
    return Path(base) / DB_FILENAME


def connect(path: str | os.PathLike[str]) -> sqlite3.Connection:
    p = Path(path)
    if str(path) != ":memory:":
        p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = DELETE")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise RuntimeError("قاعدة البيانات من إصدار أحدث من البرنامج. حدّث البرنامج أولاً.")
    for i in range(version, SCHEMA_VERSION):
        # One explicit transaction per step: the tables and the new user_version land together or not at all.
        try:
            conn.executescript(f"BEGIN;\n{MIGRATIONS[i]}\nPRAGMA user_version = {i + 1};\nCOMMIT;")
        except sqlite3.Error:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise


def _required_columns() -> dict[str, set[str]]:
    """Columns of every table in the current schema, read from a scratch in-memory database."""
    mem = sqlite3.connect(":memory:")
    try:
        for script in MIGRATIONS:
            mem.executescript(script)
        return {t: {r[1] for r in mem.execute(f"PRAGMA table_info({t})")} for t in REQUIRED_TABLES}
    finally:
        mem.close()


def check_db(path: str | os.PathLike[str]) -> str | None:
    """None when ``path`` is a sound Talabiya database; otherwise the reason (Arabic) it is not."""
    try:
        uri = Path(path).resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if not 1 <= version <= SCHEMA_VERSION:
                return "الملف ليس قاعدة بيانات طلبية أو أنه من إصدار أحدث من البرنامج"
            want = _required_columns()
            for table, cols in want.items():
                have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
                if not cols <= have:
                    return "الملف ليس قاعدة بيانات طلبية (جداول أو أعمدة ناقصة)"
            ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if ok != "ok":
                return "الملف تالف ولا يصلح للاسترجاع"
            if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
                return "الملف فيه بيانات غير مترابطة ولا يصلح للاسترجاع"
            for table in want:   # every row must actually be readable
                conn.execute(f"SELECT * FROM {table}").fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return "الملف تالف أو ليس قاعدة بيانات"
    return None


def is_talabiya_db(path: str | os.PathLike[str]) -> bool:
    """True when ``path`` is a readable, intact SQLite file with this program's schema."""
    return check_db(path) is None
