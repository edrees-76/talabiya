"""Cash-custody arithmetic (pure functions, milli-dinars).

Per restaurant and day:  remaining = received - (purchases + wage + entry fee)
Per day:                 returned  = sum(remaining);  difference = actual cash - returned
                         (negative difference = shortage, positive = surplus)
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from talabiya.core.models import Line, Sheet


def purchases(lines: Iterable[Line]) -> int:
    return sum(line.total for line in lines)


def expenses(sheet: Sheet) -> int:
    return purchases(sheet.lines) + sheet.wage + sheet.entry_fee


def remaining(sheet: Sheet) -> int:
    return sheet.received - expenses(sheet)


class SheetState(Enum):
    EMPTY = "empty"       # nothing entered
    OPEN = "open"         # in progress
    DONE = "done"         # marked complete


def sheet_state(sheet: Sheet | None) -> SheetState:
    if sheet is None or (not sheet.received and not sheet.lines and not sheet.wage and not sheet.entry_fee):
        return SheetState.EMPTY
    return SheetState.DONE if sheet.done else SheetState.OPEN


@dataclass(frozen=True)
class DayTotals:
    received: int
    expenses: int
    returned: int
    lines: int
    restaurants_with_cash: int


def day_totals(sheets: Iterable[Sheet]) -> DayTotals:
    sheets = list(sheets)
    return DayTotals(
        received=sum(s.received for s in sheets),
        expenses=sum(expenses(s) for s in sheets),
        returned=sum(remaining(s) for s in sheets),
        lines=sum(len(s.lines) for s in sheets),
        restaurants_with_cash=sum(1 for s in sheets if s.received),
    )


def difference(actual_cash: int | None, returned: int) -> int | None:
    return None if actual_cash is None else actual_cash - returned
