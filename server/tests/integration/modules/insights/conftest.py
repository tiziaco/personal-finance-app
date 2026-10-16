"""Fixtures for the insights module's integration tests."""

import pytest_asyncio

from app.modules.account.models import User


@pytest_asyncio.fixture
async def other_user(db_session):
    """A second user, to prove one user's set is invisible to another."""
    user = User(clerk_id="user_other_insights", email="other_insights@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user
