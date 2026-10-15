"""Fixtures for the analytics routes: transactions written straight to the table."""

import datetime as dt
from decimal import Decimal

import pytest
import pytest_asyncio

from app.modules.account.models import User
from app.modules.transaction.models import Transaction
from app.modules.transaction.service import fingerprint


@pytest_asyncio.fixture
async def other_user(db_session):
    user = User(clerk_id="user_other_analytics", email="other_analytics@example.com")
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
            original_category=None,
            fingerprint=fingerprint(user.id, date, merchant, value, None),
        )
        if deleted:
            txn.soft_delete()
        db_session.add(txn)
        await db_session.flush()
        return txn

    return _add
