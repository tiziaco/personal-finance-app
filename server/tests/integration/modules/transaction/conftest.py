"""Fixtures for the transaction module's integration tests."""

import datetime as dt
from decimal import Decimal

import pytest
import pytest_asyncio

from app.modules.account.models import User


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
    """Insert a transaction for a user; every field overridable. Filled in by Task 3."""

    async def _make(user, **overrides):
        raise NotImplementedError("make_transaction is implemented in Task 3")

    return _make
