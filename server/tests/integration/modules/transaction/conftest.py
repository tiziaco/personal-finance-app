"""Fixtures for the transaction module's integration tests."""

import datetime as dt
from decimal import Decimal

import pytest
import pytest_asyncio

from app.modules.account.models import User
from app.modules.transaction.models import Transaction
from app.modules.transaction.service import fingerprint


@pytest_asyncio.fixture
async def other_user(db_session):
    """A second user, to prove another user's rows answer 404."""
    user = User(clerk_id="user_other_txn", email="other_txn@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
def make_transaction(db_session):
    """Insert a transaction for a user; every field overridable."""

    async def _make(user, **overrides):
        fields = {
            "date": dt.date(2026, 3, 3),
            "merchant": "Späti",
            "amount": Decimal("-4.50"),
            "description": None,
            "category": "food_groceries",
            "confidence": 0.8,
            "is_recurring": False,
            "original_category": None,
        } | overrides
        txn = Transaction(
            user_id=user.id,
            fingerprint=fingerprint(
                user.id, fields["date"], fields["merchant"], fields["amount"], fields["description"]
            ),
            **fields,
        )
        db_session.add(txn)
        await db_session.flush()
        await db_session.refresh(txn)
        return txn

    return _make
