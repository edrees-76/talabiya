# Review prompt for Codex

Copy everything below the line into Codex (with this repository open).

---

You are reviewing **Talabiya (طلبية) 0.1.0**, a Windows desktop app (Python 3.12+, PySide6, plain SQLite)
that replaces an Excel sheet used by one person who buys daily supplies for several restaurants.
It is single-user, offline, Arabic-only (right-to-left). Read `README.md` first.

**Do not change any code.** Produce a written review only.

## How the money works (the core you must verify)
For each restaurant on each day (a "sheet"):
- `received` = cash handed to the buyer (entered manually)
- `purchases` = sum of line totals; a line total is `qty × unit_price` rounded half-up, unless the user typed a manual total
- `expenses` = purchases + `wage` ("يومية ادريس") + `entry_fee` ("رسم دخول + تحميل")
- `remaining` = received − expenses
At day close: `returned` = sum of every restaurant's remaining; `difference` = actual cash counted − returned
(negative = shortage "عجز", positive = surplus "زيادة").
Money is stored as integer **milli-dinars** (1 د.ل = 1000), quantities as decimal strings. Display: `1,234.500 د.ل`, Latin digits.

## Where things are
- `talabiya/core/` — `money.py`, `ledger.py` (pure calculations), `db.py` (schema + migrations via `PRAGMA user_version`),
  `repo.py` (all SQL), `auth.py` (scrypt password + secret question), `backup.py` (scheduled backups / restore), `seed.py`
- `talabiya/gui/` — `app.py` (start-up, login, theme, restore), `main_window.py`, `pages/*.py`, `printing.py`, `widgets.py`, `theme.py`
- `tests/` — pytest + pytest-qt (`python -m pytest tests -q`)
- `build_exe/build.sh` (PyInstaller one-folder) and `installer/talabiya.iss` (Inno Setup)

## What to look for, in priority order
1. **Wrong money**: rounding, int/float/Decimal mixing, manual-total override, blank lines, negative or huge values,
   comma vs dot decimal input, anything that could make `remaining`, `returned` or `difference` wrong.
2. **Data loss**: autosave (700 ms debounce in `pages/day_page.py`) — can typing then switching tab/day/page,
   locking, changing theme, restoring a backup or closing the window lose edits? Deleting a day, deleting a restaurant,
   emptied sheets, transactions and foreign keys (`ON DELETE CASCADE`), migrations on an existing database.
3. **Backup and restore**: `is_due` logic for daily/weekly/monthly, pruning (keep 60), restoring a non-Talabiya
   or corrupt file, a missing or unwritable backup folder, the `.before-restore.db` safety copy, the open connection during restore.
4. **Security** (proportionate to a single-user offline app): scrypt parameters, constant-time comparison, login lockout,
   secret-answer normalisation, SQL injection, file paths.
5. **Qt / UI correctness**: signals that fire twice or never, widgets used after `deleteLater`, stale state after
   restore or theme rebuild, RTL / bidi mistakes in numbers, crashes on an empty database (no restaurants, no items).
6. **Packaging**: assets found when frozen (`theme.asset` with `_MEIPASS`), missing hidden imports, the installer
   must never delete `%APPDATA%\Talabiya`.
7. **Tests**: important behaviour that has no test; propose concrete test cases (inputs and expected outputs).
8. **Suggestions**: usability improvements for the daily workflow, and code simplifications. Keep these separate from bugs.

Run the tests and, where useful, write throwaway scripts outside the repository to prove a bug before reporting it.

## Report format
Write the report **in Arabic** (keep code, file names and identifiers as they are). For each finding:
- **الخطورة**: حرج / عالٍ / متوسط / منخفض
- **المكان**: `path/file.py:line`
- **المشكلة**: one or two sentences
- **مثال يثبتها**: concrete inputs → wrong result (or the exact steps in the app)
- **الإصلاح المقترح**: short, specific

Sort findings by severity. Mark anything you could not confirm as «محتمل». Put suggestions (not bugs) in a
separate final section. If you find nothing in a category, say so in one line.
