"""The fingerprint recipe (spec §2.3), pinned to its input string."""

import datetime as dt
import hashlib
import uuid
from decimal import Decimal

import pytest

from app.modules.transaction.domain import fingerprint

pytestmark = pytest.mark.unit

USER = uuid.UUID("0199a8b0-0000-7000-8000-000000000001")


def _sha(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_recipe():
    expected = _sha(f"{USER}|2026-03-03|späti|-4.50|late snack")
    assert fingerprint(USER, dt.date(2026, 3, 3), "Späti", Decimal("-4.5"), "Late snack") == expected


def test_merchant_and_description_ignore_case_and_padding():
    a = fingerprint(USER, dt.date(2026, 3, 3), "  SPÄTI ", Decimal("-4.50"), "  LATE snack ")
    b = fingerprint(USER, dt.date(2026, 3, 3), "späti", Decimal("-4.5"), "late snack")
    assert a == b


def test_no_description_is_the_empty_string():
    expected = _sha(f"{USER}|2026-03-03|rewe|-12.70|")
    assert fingerprint(USER, dt.date(2026, 3, 3), "REWE", Decimal("-12.7"), None) == expected


def test_negative_zero_is_zero():
    assert fingerprint(USER, dt.date(2026, 3, 3), "x", Decimal("-0.00"), None) == fingerprint(
        USER, dt.date(2026, 3, 3), "x", Decimal("0"), None
    )


def test_amount_is_never_a_float():
    expected = _sha(f"{USER}|2026-03-03|x|0.10|")
    assert fingerprint(USER, dt.date(2026, 3, 3), "x", Decimal("0.1"), None) == expected
