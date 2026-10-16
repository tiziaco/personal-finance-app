"""Erasure leaves the user no insight set."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import select

from app.modules.account import user_service
from app.modules.insights.models import InsightSet
from app.modules.insights.repository import insight_repository

pytestmark = pytest.mark.integration


async def _set_for(session, user):
    return await insight_repository.replace(
        session,
        user.id,
        generated_at=datetime(2026, 10, 1, tzinfo=UTC),
        reference_month="2026-09",
        baseline_months=3,
        month_to_date_through=None,
        prompt_version="v1",
        insights=[{"title": "x"}],
    )


async def test_erase_user_deletes_the_set(db_session, test_user, other_user, stub_checkpoint_deletion):
    await _set_for(db_session, test_user)
    kept = await _set_for(db_session, other_user)

    with patch("app.modules.account.service.delete_user_memory", new=AsyncMock()):
        await user_service.erase_user(db_session, test_user)
    await db_session.flush()

    remaining = (await db_session.execute(select(InsightSet))).scalars().all()
    assert [s.id for s in remaining] == [kept.id]
