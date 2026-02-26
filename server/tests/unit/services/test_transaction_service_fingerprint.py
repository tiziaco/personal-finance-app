from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.transaction.service import TransactionService


def make_fp(**overrides):
    base = dict(
        user_id="user_abc",
        date=datetime(2026, 1, 15, tzinfo=timezone.utc),
        merchant="Netflix",
        amount=Decimal("12.99"),
        description=None,
    )
    return TransactionService.compute_fingerprint(**{**base, **overrides})


def test_fingerprint_is_deterministic():
    assert make_fp() == make_fp()


def test_fingerprint_changes_with_user_id():
    assert make_fp() != make_fp(user_id="user_xyz")


def test_fingerprint_changes_with_date():
    assert make_fp() != make_fp(date=datetime(2026, 2, 1, tzinfo=timezone.utc))


def test_fingerprint_changes_with_merchant():
    assert make_fp() != make_fp(merchant="Spotify")


def test_fingerprint_changes_with_amount():
    assert make_fp() != make_fp(amount=Decimal("9.99"))


def test_fingerprint_changes_with_description():
    assert make_fp() != make_fp(description="Payment to Alice")


def test_fingerprint_treats_none_description_as_empty_string():
    assert make_fp(description=None) == make_fp(description="")


def test_fingerprint_normalises_merchant_whitespace_and_case():
    assert make_fp(merchant="  NETFLIX  ") == make_fp(merchant="netflix")


def test_fingerprint_is_sha256_hex(monkeypatch):
    fp = make_fp()
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)
