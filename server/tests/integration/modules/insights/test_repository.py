"""The insight_set repository: one row per user, scoped by user_id."""

import datetime as dt
from datetime import UTC, datetime

import pytest
from sqlalchemy import func
from sqlmodel import select

from app.modules.insights.models import InsightSet
from app.modules.insights.repository import insight_repository

pytestmark = pytest.mark.integration


def _values(**overrides):
    return {
        "generated_at": datetime(2026, 10, 1, 8, 0, tzinfo=UTC),
        "reference_month": "2026-09",
        "baseline_months": 3,
        "month_to_date_through": dt.date(2026, 10, 1),
        "prompt_version": "v1",
        "insights": [{"title": "first"}],
    } | overrides


async def test_replace_creates_then_overwrites_one_row(db_session, test_user):
    first = await insight_repository.replace(db_session, test_user.id, **_values())
    second = await insight_repository.replace(
        db_session,
        test_user.id,
        **_values(
            generated_at=datetime(2026, 10, 2, 9, 0, tzinfo=UTC),
            reference_month="2026-10",
            baseline_months=6,
            month_to_date_through=None,
            prompt_version="v2",
            insights=[{"title": "second"}, {"title": "third"}],
        ),
    )

    count = (await db_session.execute(select(func.count()).select_from(InsightSet))).scalar_one()
    assert count == 1
    assert second.id == first.id
    stored = await insight_repository.get(db_session, test_user.id)
    assert stored.reference_month == "2026-10"
    assert stored.baseline_months == 6
    assert stored.month_to_date_through is None
    assert stored.prompt_version == "v2"
    assert stored.generated_at == datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
    assert stored.insights == [{"title": "second"}, {"title": "third"}]


async def test_get_is_scoped_to_the_user(db_session, test_user, other_user):
    await insight_repository.replace(db_session, other_user.id, **_values())

    assert await insight_repository.get(db_session, test_user.id) is None


async def test_delete_for_user_leaves_other_users_set(db_session, test_user, other_user):
    await insight_repository.replace(db_session, test_user.id, **_values())
    await insight_repository.replace(db_session, other_user.id, **_values())

    await insight_repository.delete_for_user(db_session, test_user.id)

    assert await insight_repository.get(db_session, test_user.id) is None
    assert await insight_repository.get(db_session, other_user.id) is not None
