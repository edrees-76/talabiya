"""Amounts are stored as integer milli-dinars (3 decimals, as the brand prints them: 17.400 د.ل).

Quantities are stored as decimal strings so 0.25 or 1.5 never drift.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CURRENCY = "د.ل"
_MILLI = Decimal(1000)


def to_millis(value: Decimal | float | int | str | None) -> int:
    """Dinars -> milli-dinars, half-up. Empty / invalid -> 0."""
    if value is None or value == "":
        return 0
    try:
        d = Decimal(str(value).replace(",", "").strip())
    except InvalidOperation:
        return 0
    return int((d * _MILLI).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def from_millis(millis: int) -> Decimal:
    return Decimal(millis) / _MILLI


def fmt(millis: int, *, currency: bool = False) -> str:
    """1234500 -> '1,234.500' (Latin digits, thousands separator, 3 decimals)."""
    neg = millis < 0
    whole, frac = divmod(abs(millis), 1000)
    text = f"{'-' if neg else ''}{whole:,}.{frac:03d}"
    return f"{text} {CURRENCY}" if currency else text


def parse_qty(value: Decimal | float | int | str | None) -> Decimal:
    if value is None or value == "":
        return Decimal(0)
    try:
        return Decimal(str(value).replace(",", "").strip())
    except InvalidOperation:
        return Decimal(0)


def qty_text(qty: Decimal) -> str:
    """Decimal('2.500') -> '2.5', Decimal('3') -> '3'."""
    q = qty.normalize()
    text = format(q, "f")
    return text


def line_total(qty: Decimal, unit_price_millis: int) -> int:
    """qty x unit price, rounded half-up to the milli-dinar."""
    return int((qty * Decimal(unit_price_millis)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
