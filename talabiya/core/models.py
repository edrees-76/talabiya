from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from talabiya.core.money import line_total


@dataclass
class Restaurant:
    id: int
    name: str
    note: str = ""
    active: bool = True
    sort: int = 0


@dataclass
class Item:
    id: int
    name: str
    default_unit: str = ""
    active: bool = True


@dataclass
class Line:
    item: str
    qty: Decimal = Decimal(0)
    unit: str = ""
    unit_price: int = 0          # milli-dinars
    total_override: int | None = None   # milli-dinars typed by hand
    note: str = ""

    @property
    def total(self) -> int:
        if self.total_override is not None:
            return self.total_override
        return line_total(self.qty, self.unit_price)

    @property
    def is_blank(self) -> bool:
        return not self.item.strip() and self.total == 0


@dataclass
class Sheet:
    day: str
    restaurant_id: int
    id: int | None = None
    received: int = 0
    wage: int = 0
    entry_fee: int = 0
    notes: str = ""
    done: bool = False
    lines: list[Line] = field(default_factory=list)


@dataclass
class DayClose:
    day: str
    actual_cash: int | None = None
    notes: str = ""
    closed: bool = False
    closed_at: str | None = None
