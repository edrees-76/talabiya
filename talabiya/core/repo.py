"""Data access: every read and write of the database goes through :class:`Repo`."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from talabiya.core import ledger
from talabiya.core.models import DayClose, Item, Line, Restaurant, Sheet
from talabiya.core.money import parse_qty, qty_text


class RepoError(ValueError):
    """A user-facing refusal (message is Arabic and says what to do)."""


@dataclass(frozen=True)
class HistoryRow:
    day: str
    restaurants: int
    received: int
    expenses: int
    returned: int
    actual_cash: int | None
    closed: bool


@dataclass(frozen=True)
class PriceChange:
    item: str
    unit: str
    previous: int
    latest: int
    latest_day: str

    @property
    def change_pct(self) -> float:
        return 0.0 if self.previous == 0 else (self.latest - self.previous) / self.previous * 100


@dataclass(frozen=True)
class ItemSpend:
    item: str
    total: int
    qty_text: str


def _iso(d: date) -> str:
    return d.isoformat()


class Repo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ---------------------------------------------------------------- settings
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str | None) -> None:
        with self.conn:
            if value is None:
                self.conn.execute("DELETE FROM settings WHERE key=?", (key,))
            else:
                self.conn.execute(
                    "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, value),
                )

    # ------------------------------------------------------------- restaurants
    def restaurants(self, *, include_inactive: bool = False) -> list[Restaurant]:
        sql = "SELECT * FROM restaurants" + ("" if include_inactive else " WHERE active=1") + " ORDER BY sort, id"
        return [Restaurant(r["id"], r["name"], r["note"], bool(r["active"]), r["sort"]) for r in self.conn.execute(sql)]

    def add_restaurant(self, name: str, note: str = "") -> int:
        name = name.strip()
        if not name:
            raise RepoError("أدخل اسم المطعم")
        try:
            with self.conn:
                sort = self.conn.execute("SELECT COALESCE(MAX(sort),0)+1 FROM restaurants").fetchone()[0]
                cur = self.conn.execute(
                    "INSERT INTO restaurants(name,note,sort) VALUES(?,?,?)", (name, note.strip(), sort)
                )
        except sqlite3.IntegrityError as e:
            raise RepoError(f"يوجد مطعم بالاسم «{name}». اختر اسماً آخر") from e
        return int(cur.lastrowid or 0)

    def update_restaurant(self, rid: int, name: str, note: str = "") -> None:
        name = name.strip()
        if not name:
            raise RepoError("أدخل اسم المطعم")
        try:
            with self.conn:
                self.conn.execute("UPDATE restaurants SET name=?, note=? WHERE id=?", (name, note.strip(), rid))
        except sqlite3.IntegrityError as e:
            raise RepoError(f"يوجد مطعم بالاسم «{name}». اختر اسماً آخر") from e

    def set_restaurant_active(self, rid: int, active: bool) -> None:
        with self.conn:
            self.conn.execute("UPDATE restaurants SET active=? WHERE id=?", (int(active), rid))

    def restaurant_has_sheets(self, rid: int) -> bool:
        return self.conn.execute("SELECT 1 FROM day_sheets WHERE restaurant_id=? LIMIT 1", (rid,)).fetchone() is not None

    def delete_restaurant(self, rid: int) -> None:
        if self.restaurant_has_sheets(rid):
            raise RepoError("لهذا المطعم مشتريات مسجلة. أوقفه بدلاً من حذفه")
        with self.conn:
            self.conn.execute("DELETE FROM restaurants WHERE id=?", (rid,))

    def move_restaurant(self, rid: int, step: int) -> None:
        rows = self.restaurants(include_inactive=True)
        ids = [r.id for r in rows]
        i = ids.index(rid)
        j = i + step
        if not 0 <= j < len(ids):
            return
        ids[i], ids[j] = ids[j], ids[i]
        with self.conn:
            for n, x in enumerate(ids):
                self.conn.execute("UPDATE restaurants SET sort=? WHERE id=?", (n + 1, x))

    # ------------------------------------------------------------ units/items
    def units(self) -> list[str]:
        return [r[0] for r in self.conn.execute("SELECT name FROM units ORDER BY sort, id")]

    def add_unit(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise RepoError("أدخل اسم الوحدة")
        try:
            with self.conn:
                sort = self.conn.execute("SELECT COALESCE(MAX(sort),0)+1 FROM units").fetchone()[0]
                self.conn.execute("INSERT INTO units(name,sort) VALUES(?,?)", (name, sort))
        except sqlite3.IntegrityError as e:
            raise RepoError(f"الوحدة «{name}» موجودة") from e

    def rename_unit(self, old: str, new: str) -> None:
        new = new.strip()
        if not new:
            raise RepoError("أدخل اسم الوحدة")
        try:
            with self.conn:
                self.conn.execute("UPDATE units SET name=? WHERE name=?", (new, old))
                self.conn.execute("UPDATE items SET default_unit=? WHERE default_unit=?", (new, old))
                self.conn.execute("UPDATE purchase_lines SET unit=? WHERE unit=?", (new, old))
        except sqlite3.IntegrityError as e:
            raise RepoError(f"الوحدة «{new}» موجودة") from e

    def delete_unit(self, name: str) -> None:
        used = self.conn.execute("SELECT 1 FROM purchase_lines WHERE unit=? LIMIT 1", (name,)).fetchone()
        if used:
            raise RepoError(f"الوحدة «{name}» مستخدمة في مشتريات سابقة ولا يمكن حذفها")
        with self.conn:
            self.conn.execute("DELETE FROM units WHERE name=?", (name,))
            self.conn.execute("UPDATE items SET default_unit='' WHERE default_unit=?", (name,))

    def items(self, *, include_inactive: bool = False) -> list[Item]:
        sql = "SELECT * FROM items" + ("" if include_inactive else " WHERE active=1") + " ORDER BY name"
        return [Item(r["id"], r["name"], r["default_unit"], bool(r["active"])) for r in self.conn.execute(sql)]

    def add_item(self, name: str, default_unit: str = "") -> int:
        name = " ".join(name.split())
        if not name:
            raise RepoError("أدخل اسم الصنف")
        try:
            with self.conn:
                cur = self.conn.execute("INSERT INTO items(name,default_unit) VALUES(?,?)", (name, default_unit))
        except sqlite3.IntegrityError as e:
            raise RepoError(f"الصنف «{name}» موجود") from e
        return int(cur.lastrowid or 0)

    def ensure_item(self, name: str, default_unit: str = "") -> None:
        name = " ".join(name.split())
        if name:
            with self.conn:
                self.conn.execute("INSERT OR IGNORE INTO items(name,default_unit) VALUES(?,?)", (name, default_unit))

    def update_item(self, iid: int, name: str, default_unit: str) -> None:
        name = " ".join(name.split())
        if not name:
            raise RepoError("أدخل اسم الصنف")
        try:
            with self.conn:
                self.conn.execute("UPDATE items SET name=?, default_unit=? WHERE id=?", (name, default_unit, iid))
        except sqlite3.IntegrityError as e:
            raise RepoError(f"الصنف «{name}» موجود") from e

    def set_item_active(self, iid: int, active: bool) -> None:
        with self.conn:
            self.conn.execute("UPDATE items SET active=? WHERE id=?", (int(active), iid))

    def seed_catalog(self, units: list[str], items: list[tuple[str, str]]) -> None:
        with self.conn:
            for n, u in enumerate(units, 1):
                self.conn.execute("INSERT OR IGNORE INTO units(name,sort) VALUES(?,?)", (u, n))
            for name, unit in items:
                self.conn.execute("INSERT OR IGNORE INTO items(name,default_unit) VALUES(?,?)", (name, unit))

    # ------------------------------------------------------------------ sheets
    def _row_to_sheet(self, r: sqlite3.Row) -> Sheet:
        s = Sheet(
            day=r["day"], restaurant_id=r["restaurant_id"], id=r["id"], received=r["received"],
            wage=r["wage"], entry_fee=r["entry_fee"], notes=r["notes"], done=bool(r["done"]),
        )
        s.lines = [
            Line(
                item=x["item"], qty=parse_qty(x["qty"]), unit=x["unit"], unit_price=x["unit_price"],
                total_override=x["total"] if x["total_manual"] else None, note=x["note"],
            )
            for x in self.conn.execute("SELECT * FROM purchase_lines WHERE sheet_id=? ORDER BY seq", (s.id,))
        ]
        return s

    def sheet(self, day: str, restaurant_id: int) -> Sheet:
        """The saved sheet, or a new empty (unsaved, id=None) one."""
        r = self.conn.execute(
            "SELECT * FROM day_sheets WHERE day=? AND restaurant_id=?", (day, restaurant_id)
        ).fetchone()
        return self._row_to_sheet(r) if r else Sheet(day=day, restaurant_id=restaurant_id)

    def sheets_for_day(self, day: str) -> list[Sheet]:
        rows = self.conn.execute("SELECT * FROM day_sheets WHERE day=? ORDER BY restaurant_id", (day,)).fetchall()
        return [self._row_to_sheet(r) for r in rows]

    def save_sheet(self, sheet: Sheet) -> int:
        """Insert or replace the sheet and all its lines. Blank lines are dropped.

        An empty sheet that was never saved is not written; a saved sheet that became empty is deleted.
        """
        lines = [ln for ln in sheet.lines if not ln.is_blank]
        empty = not (sheet.received or sheet.wage or sheet.entry_fee or lines or sheet.notes.strip() or sheet.done)
        with self.conn:
            if empty:
                if sheet.id is not None:
                    self.conn.execute("DELETE FROM day_sheets WHERE id=?", (sheet.id,))
                    sheet.id = None
                return 0
            self.conn.execute(
                """INSERT INTO day_sheets(day,restaurant_id,received,wage,entry_fee,notes,done)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(day,restaurant_id) DO UPDATE SET received=excluded.received, wage=excluded.wage,
                     entry_fee=excluded.entry_fee, notes=excluded.notes, done=excluded.done""",
                (sheet.day, sheet.restaurant_id, sheet.received, sheet.wage, sheet.entry_fee, sheet.notes,
                 int(sheet.done)),
            )
            sid = self.conn.execute(
                "SELECT id FROM day_sheets WHERE day=? AND restaurant_id=?", (sheet.day, sheet.restaurant_id)
            ).fetchone()[0]
            sheet.id = sid
            self.conn.execute("DELETE FROM purchase_lines WHERE sheet_id=?", (sid,))
            for seq, ln in enumerate(lines, 1):
                name = " ".join(ln.item.split())
                self.conn.execute(
                    """INSERT INTO purchase_lines(sheet_id,seq,item,qty,unit,unit_price,total,total_manual,note)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (sid, seq, name, qty_text(ln.qty), ln.unit, ln.unit_price, ln.total,
                     int(ln.total_override is not None), ln.note),
                )
                if name:
                    self.conn.execute("INSERT OR IGNORE INTO items(name,default_unit) VALUES(?,?)", (name, ln.unit))
        return int(sid)

    def delete_day(self, day: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM day_sheets WHERE day=?", (day,))
            self.conn.execute("DELETE FROM day_close WHERE day=?", (day,))

    # ---------------------------------------------------------------- closing
    def day_close(self, day: str) -> DayClose:
        r = self.conn.execute("SELECT * FROM day_close WHERE day=?", (day,)).fetchone()
        if not r:
            return DayClose(day=day)
        return DayClose(day, r["actual_cash"], r["notes"], bool(r["closed"]), r["closed_at"])

    def save_day_close(self, dc: DayClose) -> None:
        with self.conn:
            if dc.actual_cash is None and not dc.notes.strip() and not dc.closed:
                self.conn.execute("DELETE FROM day_close WHERE day=?", (dc.day,))
                return
            self.conn.execute(
                """INSERT INTO day_close(day,actual_cash,notes,closed,closed_at) VALUES(?,?,?,?,?)
                   ON CONFLICT(day) DO UPDATE SET actual_cash=excluded.actual_cash, notes=excluded.notes,
                     closed=excluded.closed, closed_at=excluded.closed_at""",
                (dc.day, dc.actual_cash, dc.notes, int(dc.closed), dc.closed_at),
            )

    def close_day(self, day: str, actual_cash: int, notes: str = "") -> DayClose:
        dc = DayClose(day, actual_cash, notes, True, datetime.now().isoformat(timespec="minutes"))
        self.save_day_close(dc)
        return dc

    def reopen_day(self, day: str) -> None:
        dc = self.day_close(day)
        dc.closed, dc.closed_at = False, None
        self.save_day_close(dc)

    # ---------------------------------------------------------------- history
    def history(self, start: str, end: str) -> list[HistoryRow]:
        days = [r[0] for r in self.conn.execute(
            """SELECT day FROM day_sheets WHERE day BETWEEN ? AND ?
               UNION SELECT day FROM day_close WHERE day BETWEEN ? AND ? ORDER BY day DESC""",
            (start, end, start, end),
        )]
        out: list[HistoryRow] = []
        for d in days:
            sheets = self.sheets_for_day(d)
            t = ledger.day_totals(sheets)
            dc = self.day_close(d)
            out.append(HistoryRow(d, len(sheets), t.received, t.expenses, t.returned, dc.actual_cash, dc.closed))
        return out

    def unclosed_days(self, before: str, limit: int = 5) -> list[str]:
        rows = self.conn.execute(
            """SELECT DISTINCT s.day FROM day_sheets s LEFT JOIN day_close c ON c.day=s.day
               WHERE s.day < ? AND COALESCE(c.closed,0)=0 ORDER BY s.day DESC LIMIT ?""",
            (before, limit),
        )
        return [r[0] for r in rows]

    # -------------------------------------------------------------- dashboard
    def daily_expenses(self, end: date, days: int) -> list[tuple[str, int]]:
        start = end - timedelta(days=days - 1)
        out = []
        for i in range(days):
            d = _iso(start + timedelta(days=i))
            out.append((d, ledger.day_totals(self.sheets_for_day(d)).expenses))
        return out

    def month_by_restaurant(self, month_start: date, month_end: date) -> list[tuple[str, int]]:
        rows = self.conn.execute(
            """SELECT r.name, s.wage + s.entry_fee
                      + COALESCE((SELECT SUM(total) FROM purchase_lines l WHERE l.sheet_id=s.id),0) AS spent
               FROM day_sheets s JOIN restaurants r ON r.id=s.restaurant_id
               WHERE s.day BETWEEN ? AND ?""",
            (_iso(month_start), _iso(month_end)),
        )
        acc: dict[str, int] = {}
        for name, spent in rows:
            acc[name] = acc.get(name, 0) + spent
        return sorted(acc.items(), key=lambda kv: kv[1], reverse=True)

    def top_items(self, start: date, end: date, limit: int = 5) -> list[ItemSpend]:
        rows = self.conn.execute(
            """SELECT l.item, SUM(l.total) AS tot FROM purchase_lines l JOIN day_sheets s ON s.id=l.sheet_id
               WHERE s.day BETWEEN ? AND ? GROUP BY l.item ORDER BY tot DESC LIMIT ?""",
            (_iso(start), _iso(end), limit),
        ).fetchall()
        out = []
        for item, tot in rows:
            per_unit: dict[str, Decimal] = {}
            for q, u in self.conn.execute(
                """SELECT l.qty, l.unit FROM purchase_lines l JOIN day_sheets s ON s.id=l.sheet_id
                   WHERE l.item=? AND s.day BETWEEN ? AND ?""",
                (item, _iso(start), _iso(end)),
            ):
                per_unit[u] = per_unit.get(u, Decimal(0)) + parse_qty(q)
            qtxt = "، ".join(f"{qty_text(q)} {u}".strip() for u, q in per_unit.items())
            out.append(ItemSpend(item, tot, qtxt))
        return out

    def price_changes(self, upto: str, limit: int = 6) -> list[PriceChange]:
        """For items bought at least twice (same unit), the latest unit price vs the one before."""
        rows = self.conn.execute(
            """SELECT l.item, l.unit, l.unit_price, s.day FROM purchase_lines l JOIN day_sheets s ON s.id=l.sheet_id
               WHERE s.day <= ? AND l.unit_price > 0 ORDER BY s.day DESC, l.id DESC""",
            (upto,),
        )
        seen: dict[tuple[str, str], list[tuple[int, str]]] = {}
        for item, unit, price, day in rows:
            lst = seen.setdefault((item, unit), [])
            if len(lst) < 2 and (not lst or lst[0][1] != day):
                lst.append((price, day))
        changes = [
            PriceChange(item, unit, prev[0], last[0], last[1])
            for (item, unit), lst in seen.items()
            if len(lst) == 2
            for last, prev in [(lst[0], lst[1])]
        ]
        changes.sort(key=lambda c: (c.latest_day, abs(c.change_pct)), reverse=True)
        return changes[:limit]
