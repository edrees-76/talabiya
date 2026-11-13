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
        with conn:
            conn.executescript(MIGRATIONS[i])
            conn.execute(f"PRAGMA user_version = {i + 1}")


def is_talabiya_db(path: str | os.PathLike[str]) -> bool:
    """True when ``path`` is a readable SQLite file with this program's tables."""
    try:
        uri = Path(path).resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            version = conn.execute("PRAGMA user_version").fetchone()[0]
        finally:
            conn.close()
    except sqlite3.Error:
        return False
    return REQUIRED_TABLES <= names and 1 <= version <= SCHEMA_VERSION
