"""Plain rows for the analytics domain tests: AnalysisRow's seven fields, nothing else."""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.modules.transaction.domain import normalise_merchant


@dataclass(frozen=True)
class Row:
    date: dt.date
    merchant: str
    merchant_key: str
    amount: Decimal
    category: str
    is_recurring: bool
    recurring_source: str = "detected"


def row(
    day: str,
    amount: str,
    merchant: str = "Shop",
    category: str = "shopping",
    recurring: bool = False,
    key: Optional[str] = None,
    source: str = "detected",
) -> Row:
    """`row("2026-03-01", "-12.50")` — a day in ISO form and a signed decimal string.

    The merchant key is the stored one, `normalise_merchant(merchant)`, unless `key` is given.
    """
    merchant_key = normalise_merchant(merchant) if key is None else key
    return Row(dt.date.fromisoformat(day), merchant, merchant_key, Decimal(amount), category, recurring, source)
