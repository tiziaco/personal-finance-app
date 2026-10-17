"""Fixtures for the insights module's integration tests."""

import datetime as dt
from decimal import Decimal

import pytest
import pytest_asyncio

from app.modules.account.models import User
from app.modules.transaction.domain import USER, fingerprint, normalise_merchant
from app.modules.transaction.models import Transaction


@pytest_asyncio.fixture
async def other_user(db_session):
    """A second user, to prove one user's set is invisible to another."""
    user = User(clerk_id="user_other_insights", email="other_insights@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
def add(db_session):
    """add(user, "2026-09-05", "-200.00", category=..., merchant=..., recurring=..., deleted=...)"""

    async def _add(user, day, amount, category="food_groceries", merchant="Shop", recurring=False, deleted=False):
        date, value = dt.date.fromisoformat(day), Decimal(amount)
        txn = Transaction(
            user_id=user.id,
            date=date,
            merchant=merchant,
            amount=value,
            description=None,
            category=category,
            confidence=1.0,
            is_recurring=recurring,
            recurring_source=USER,
            original_category=None,
            fingerprint=fingerprint(user.id, date, merchant, value, None),
            merchant_key=normalise_merchant(merchant),
        )
        if deleted:
            txn.soft_delete()
        db_session.add(txn)
        await db_session.flush()
        return txn

    return _add
