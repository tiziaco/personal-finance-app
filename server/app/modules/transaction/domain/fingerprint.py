"""The duplicate key (docs/data-model/transaction.md, D3)."""

import datetime as dt
import hashlib
import uuid
from decimal import Decimal
from typing import Optional

_CENT = Decimal("0.01")


def fingerprint(user_id: uuid.UUID, date: dt.date, merchant: str, amount: Decimal, description: Optional[str]) -> str:
    """sha256 of user|date|merchant|amount|description — the duplicate key (docs/data-model/transaction.md).

    Merchant and description are stripped and casefolded; the amount is the
    Decimal at two places, never a float, and -0.00 is 0.00. The import uses
    the same function, so the two can never disagree.
    """
    cents = amount.quantize(_CENT)
    if cents == 0:
        cents = Decimal("0.00")
    raw = (
        f"{user_id}|{date:%Y-%m-%d}|{merchant.strip().casefold()}|{cents:.2f}|{(description or '').strip().casefold()}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
