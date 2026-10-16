"""Erasure leaves the user no insight set."""

import datetime as dt
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import select

from app.core.events import events
from app.modules.account import USER_ERASING, user_service
from app.modules.insights.models import InsightSet
from app.modules.insights.repository import insight_repository
from app.modules.transaction import TRANSACTIONS_ALL_DELETED, transaction_service
from app.modules.transaction.schemas import TransactionCreate

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


async def test_delete_all_route_deletes_the_insight_set(authenticated_client, db_session, test_user, other_user):
    await transaction_service.create(
        db_session,
        test_user.id,
        TransactionCreate(date=dt.date(2026, 3, 3), merchant="Spati", amount="-4.50", category="food_groceries"),
    )
    await _set_for(db_session, test_user)
    kept = await _set_for(db_session, other_user)

    response = await authenticated_client.delete("/api/v1/transactions")

    assert response.status_code == 200
    remaining = (await db_session.execute(select(InsightSet))).scalars().all()
    assert [s.id for s in remaining] == [kept.id]


async def test_erasure_does_not_publish_all_deleted(db_session, test_user, stub_checkpoint_deletion):
    with (
        patch("app.modules.account.service.delete_user_memory", new=AsyncMock()),
        patch.object(events, "publish", wraps=events.publish) as publish,
    ):
        await user_service.erase_user(db_session, test_user)

    published = [call.args[0] for call in publish.call_args_list]
    assert USER_ERASING in published
    assert TRANSACTIONS_ALL_DELETED not in published
