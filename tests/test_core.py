from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from talabiya.core import auth, backup, ledger
from talabiya.core.db import connect, is_talabiya_db
from talabiya.core.models import Line, Sheet
from talabiya.core.money import fmt, line_total, to_millis
from talabiya.core.repo import RepoError
from talabiya.core.seed import ITEMS, UNITS


# ------------------------------------------------------------------ money
def test_money_roundtrip_and_format():
    assert to_millis("17.4") == 17400
    assert to_millis(0.055) == 55
    assert to_millis("") == 0 and to_millis("abc") == 0
    assert fmt(17400) == "17.400"
    assert fmt(1234500, currency=True) == "1,234.500 د.ل"
    assert fmt(-10000) == "-10.000"


def test_line_total_half_up():
    assert line_total(Decimal("600"), 55) == 33000          # 600 x 0.055 = 33.000 (Excel row)
    assert line_total(Decimal("2.5"), 3333) == 8333           # 8.3325 -> 8.333
    assert line_total(Decimal("0.5"), 3) == 2                 # 0.0015 -> 0.002 (half-up)


# ----------------------------------------------------------------- ledger
def _excel_mazaqi() -> Sheet:
    """«مطعم مذاقى» on 12-11-2026 in the workbook: received 300, wage 50, fee 2."""
    s = Sheet(day="2026-11-12", restaurant_id=1, received=300_000, wage=50_000, entry_fee=2_000)
    for name, q, price in [("سلاطة", 3, 30), ("فلفل حلو", 2, 5), ("هريسة", 5, 7), ("فلفل حار", 2, 5),
                           ("شكاير زبون سوداء", 2, 15), ("كسبر", 1, 18)]:
        s.lines.append(Line(name, Decimal(q), "كجم", to_millis(price)))
    return s


def test_ledger_matches_workbook_day():
    s = _excel_mazaqi()
    assert ledger.purchases(s.lines) == 193_000
    assert ledger.expenses(s) == 245_000
    assert ledger.remaining(s) == 55_000


def test_ledger_day_totals_and_difference():
    a = _excel_mazaqi()
    b = Sheet(day="2026-11-12", restaurant_id=2, received=100_000, lines=[Line("ليم", Decimal(2), "كجم", 5000)])
    t = ledger.day_totals([a, b])
    assert t.received == 400_000 and t.expenses == 255_000 and t.returned == 145_000
    assert ledger.difference(None, t.returned) is None
    assert ledger.difference(140_000, t.returned) == -5_000   # shortage
    assert ledger.difference(145_000, t.returned) == 0


def test_manual_total_overrides_qty_times_price():
    ln = Line("علب هريسة 20×20", Decimal(600), "قطعة", 0, total_override=33_000)
    assert ln.total == 33_000


def test_sheet_state():
    assert ledger.sheet_state(None) is ledger.SheetState.EMPTY
    s = Sheet(day="d", restaurant_id=1)
    assert ledger.sheet_state(s) is ledger.SheetState.EMPTY
    s.received = 1
    assert ledger.sheet_state(s) is ledger.SheetState.OPEN
    s.done = True
    assert ledger.sheet_state(s) is ledger.SheetState.DONE


# ------------------------------------------------------------------- repo
def test_starts_without_restaurants(repo):
    assert repo.restaurants() == []
    assert len(repo.units()) == len(UNITS)
    assert len(repo.items()) == len(ITEMS)


def test_restaurant_crud(repo):
    rid = repo.add_restaurant("  مطعم العاصمة ")
    assert [r.name for r in repo.restaurants()] == ["مطعم العاصمة"]
    with pytest.raises(RepoError):
        repo.add_restaurant("مطعم العاصمة")
    with pytest.raises(RepoError):
        repo.add_restaurant("  ")
    repo.set_restaurant_active(rid, False)
    assert repo.restaurants() == [] and len(repo.restaurants(include_inactive=True)) == 1
    repo.delete_restaurant(rid)
    assert repo.restaurants(include_inactive=True) == []


def test_cannot_delete_restaurant_with_purchases(repo):
    rid = repo.add_restaurant("مذاقى")
    s = _excel_mazaqi()
    s.restaurant_id = rid
    repo.save_sheet(s)
    with pytest.raises(RepoError):
        repo.delete_restaurant(rid)


def test_save_and_reload_sheet(repo):
    rid = repo.add_restaurant("مذاقى")
    s = _excel_mazaqi()
    s.restaurant_id = rid
    s.lines.append(Line("", Decimal(0), "", 0))                          # blank row is dropped
    s.lines.append(Line("صنف جديد", Decimal("0.5"), "كجم", 10_000))       # new item is learned
    repo.save_sheet(s)
    back = repo.sheet("2026-11-12", rid)
    assert back.id is not None
    assert len(back.lines) == 7
    assert back.lines[-1].qty == Decimal("0.5") and back.lines[-1].total == 5_000
    assert ledger.remaining(back) == 50_000
    assert "صنف جديد" in {i.name for i in repo.items()}
    # editing replaces the lines
    back.lines = back.lines[:1]
    repo.save_sheet(back)
    assert len(repo.sheet("2026-11-12", rid).lines) == 1


def test_empty_sheet_not_saved_and_emptied_sheet_deleted(repo):
    rid = repo.add_restaurant("أ")
    s = repo.sheet("2026-11-13", rid)
    assert repo.save_sheet(s) == 0 and repo.sheets_for_day("2026-11-13") == []
    s.received = 1000
    repo.save_sheet(s)
    assert len(repo.sheets_for_day("2026-11-13")) == 1
    s.received = 0
    repo.save_sheet(s)
    assert repo.sheets_for_day("2026-11-13") == []


def test_close_history_and_delete_day(repo):
    rid = repo.add_restaurant("مذاقى")
    s = _excel_mazaqi()
    s.restaurant_id = rid
    repo.save_sheet(s)
    assert repo.unclosed_days("2026-11-13") == ["2026-11-12"]
    repo.close_day("2026-11-12", 50_000, "نقص 5")
    assert repo.unclosed_days("2026-11-13") == []
    h = repo.history("2026-11-01", "2026-11-30")
    assert len(h) == 1 and h[0].returned == 55_000 and h[0].actual_cash == 50_000 and h[0].closed
    repo.reopen_day("2026-11-12")
    assert not repo.day_close("2026-11-12").closed
    repo.delete_day("2026-11-12")
    assert repo.history("2026-11-01", "2026-11-30") == []


def test_dashboard_queries(repo):
    a = repo.add_restaurant("أ")
    b = repo.add_restaurant("ب")
    d1, d2 = date(2026, 11, 11), date(2026, 11, 12)
    repo.save_sheet(Sheet(d1.isoformat(), a, received=500_000,
                          lines=[Line("طماطم", Decimal(10), "كجم", 4000), Line("ارز", Decimal(1), "شوال", 140_000)]))
    repo.save_sheet(Sheet(d2.isoformat(), a, received=500_000, wage=50_000,
                          lines=[Line("طماطم", Decimal(10), "كجم", 3500)]))
    repo.save_sheet(Sheet(d2.isoformat(), b, received=100_000, lines=[Line("طماطم", Decimal(2), "كجم", 3500)]))
    week = repo.daily_expenses(d2, 3)
    assert week == [("2026-11-10", 0), ("2026-11-11", 180_000), ("2026-11-12", 92_000)]
    by_r = dict(repo.month_by_restaurant(date(2026, 11, 1), date(2026, 11, 30)))
    assert by_r == {"أ": 265_000, "ب": 7_000}
    top = repo.top_items(date(2026, 11, 1), date(2026, 11, 30))
    assert top[0].item == "ارز" and top[1].item == "طماطم" and top[1].qty_text == "22 كجم"
    changes = repo.price_changes("2026-11-12")
    assert len(changes) == 1 and changes[0].item == "طماطم"
    assert changes[0].previous == 4000 and changes[0].latest == 3500 and round(changes[0].change_pct) == -12


def test_units_and_items(repo):
    repo.add_unit("لتر")
    with pytest.raises(RepoError):
        repo.add_unit("لتر")
    repo.rename_unit("لتر", "ليتر")
    assert "ليتر" in repo.units()
    rid = repo.add_restaurant("أ")
    repo.save_sheet(Sheet("2026-11-13", rid, lines=[Line("حليب", Decimal(1), "ليتر", 1000)]))
    with pytest.raises(RepoError):
        repo.delete_unit("ليتر")
    repo.delete_unit("ملل")
    assert "ملل" not in repo.units()
    iid = repo.add_item("صنف تجريبي", "كجم")
    repo.set_item_active(iid, False)
    assert "صنف تجريبي" not in {i.name for i in repo.items()}


def test_move_restaurant(repo):
    a, b = repo.add_restaurant("أ"), repo.add_restaurant("ب")
    repo.move_restaurant(b, -1)
    assert [r.id for r in repo.restaurants()] == [b, a]


# ------------------------------------------------------------------- auth
def test_auth_flow(repo):
    assert not auth.is_configured(repo)
    with pytest.raises(RepoError):
        auth.setup(repo, "12", "سؤال", "جواب")
    auth.setup(repo, "1234", "ما اسم أول مدرسة؟", "  مدرسة الأمل ")
    assert auth.is_configured(repo) and auth.check_password(repo, "1234") and not auth.check_password(repo, "x")
    assert "1234" not in (repo.get_setting("password_hash") or "")
    with pytest.raises(RepoError):
        auth.reset_with_answer(repo, "خطأ", "9999")
    auth.reset_with_answer(repo, "مدرسه الامل", "9999")        # letter variants and spacing ignored
    assert auth.check_password(repo, "9999")
    with pytest.raises(RepoError):
        auth.change_password(repo, "1234", "5555")
    auth.change_password(repo, "9999", "5555")
    assert auth.check_password(repo, "5555")


# ----------------------------------------------------------------- backup
def test_backup_due():
    now = datetime(2026, 11, 13, 9, 0)
    assert backup.is_due("daily", None, now)
    assert not backup.is_due("daily", now - timedelta(hours=5), now)
    assert backup.is_due("daily", now - timedelta(days=1), now)
    assert not backup.is_due("weekly", now - timedelta(days=6), now)
    assert backup.is_due("monthly", now - timedelta(days=31), now)
    assert not backup.is_due("off", None, now)


def test_backup_run_and_restore(repo, tmp_path):
    rid = repo.add_restaurant("أ")
    dest = tmp_path / "نسخ"
    assert backup.run_if_due(repo) is None                     # no folder chosen yet
    repo.set_setting("backup_folder", str(dest))
    f = backup.run_if_due(repo, datetime(2026, 11, 13, 8, 0))
    assert f is not None and f.exists() and is_talabiya_db(f)
    assert backup.run_if_due(repo, datetime(2026, 11, 13, 12, 0)) is None   # daily: not again today
    # restore into a separate database file
    db2 = tmp_path / "other.db"
    connect(db2).close()
    backup.restore(f, db2)
    c = connect(db2)
    assert [r["name"] for r in c.execute("SELECT name FROM restaurants")] == ["أ"]
    c.close()
    assert (tmp_path / "other.before-restore.db").exists()
    bad = tmp_path / "bad.db"
    bad.write_text("not a db")
    with pytest.raises(RepoError):
        backup.restore(bad, db2)
    assert rid


def test_backup_prune(repo, tmp_path):
    for i in range(5):
        backup.make_backup(repo, tmp_path, datetime(2026, 11, 1 + i))
    backup.prune(tmp_path, keep=3)
    assert len(backup.list_backups(tmp_path)) == 3
