"""Plain rows for the analytics domain tests: AnalysisRow's five fields, nothing else."""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Row:
    date: dt.date
    merchant: str
    amount: Decimal
    category: str
    is_recurring: bool


def row(day: str, amount: str, merchant: str = "Shop", category: str = "shopping", recurring: bool = False) -> Row:
    """`row("2026-03-01", "-12.50")` — a day in ISO form and a signed decimal string."""
    return Row(dt.date.fromisoformat(day), merchant, Decimal(amount), category, recurring)
