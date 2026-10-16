"""The insights service against a real database; the model is patched."""

import datetime as dt
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.insights import InsightLink, KeyFigure, WrittenInsight
from app.agents.shared.structured import InvalidModelAnswer
from app.modules.analytics import service as analytics_service_module
from app.modules.insights import service as insights_service_module
from app.modules.insights.exceptions import InsightsUnavailableError
from app.modules.insights.repository import insight_repository
from app.modules.insights.service import insights_service

pytestmark = pytest.mark.integration

TODAY = dt.date(2026, 10, 16)
LONG_AGO = dt.datetime(2026, 9, 1, tzinfo=dt.UTC)


@pytest.fixture(autouse=True)
def today(monkeypatch):
    monkeypatch.setattr(insights_service_module, "_today", lambda: TODAY)
    monkeypatch.setattr(analytics_service_module, "_today", lambda: TODAY)
    return TODAY


def _written() -> list[WrittenInsight]:
    return [
        WrittenInsight(
            section="spending",
            severity="high",
            period="month",
            summary="Groceries rose",
            narrative="You spent more on groceries.",
            key_figure=KeyFigure(kind="amount", value=Decimal("200.50"), qualifier="in September"),
            link=InsightLink(kind="category", category="food_groceries", merchant=None),
        )
    ]


def model(result=None, error=None):
    mock = AsyncMock(return_value=result if result is not None else _written(), side_effect=error)
    return patch("app.modules.insights.service.write_insights", mock), mock


async def aged(add, user, day="2026-09-05", **kwargs):
    """A transaction whose last change is long before any generation."""
    txn = await add(user, day, "-200.00", **kwargs)
    txn.updated_at = LONG_AGO
    return txn


async def test_read_no_data_hides_an_existing_set(db_session, test_user):
    await insight_repository.replace(
        db_session,
        test_user.id,
        generated_at=dt.datetime.now(dt.UTC),
        reference_month="2026-09",
        baseline_months=1,
        month_to_date_through=None,
        prompt_version="v1",
        insights=[],
    )

    response = await insights_service.read(db_session, test_user.id)

    assert response.status == "no_data"
    assert response.insights == []
    assert response.generated_at is None and response.reference_month is None


async def test_read_none_then_fresh_after_generate(db_session, test_user, add):
    await aged(add, test_user)
    await db_session.flush()
    assert (await insights_service.read(db_session, test_user.id)).status == "none"

    patcher, mock = model()
    with patcher:
        generated = await insights_service.generate(db_session, test_user.id)
    read = await insights_service.read(db_session, test_user.id)

    assert generated.status == "fresh"
    mock.assert_awaited_once()
    assert read.status == "fresh"
    assert read.reference_month == "2026-09"
    assert read.insights[0].key_figure.value == Decimal("200.50")
    assert read.insights[0].link.category == "food_groceries"
    assert read.insights == generated.insights


async def test_read_stale_after_an_edit(db_session, test_user, add):
    await aged(add, test_user)
    patcher, _ = model()
    with patcher:
        await insights_service.generate(db_session, test_user.id)

    await add(test_user, "2026-09-06", "-5.00", merchant="Other")

    assert (await insights_service.read(db_session, test_user.id)).status == "stale"


async def test_read_stale_after_a_soft_delete(db_session, test_user, add):
    await aged(add, test_user)
    doomed = await aged(add, test_user, "2026-09-07", merchant="Gone")
    patcher, _ = model()
    with patcher:
        await insights_service.generate(db_session, test_user.id)

    doomed.soft_delete()
    doomed.updated_at = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=1)
    await db_session.flush()

    assert (await insights_service.read(db_session, test_user.id)).status == "stale"


async def test_read_stale_when_the_month_rolled_over(db_session, test_user, add, monkeypatch):
    await aged(add, test_user)
    await insight_repository.replace(
        db_session,
        test_user.id,
        generated_at=dt.datetime(2026, 9, 30, 12, tzinfo=dt.UTC),
        reference_month="2026-08",
        baseline_months=0,
        month_to_date_through=None,
        prompt_version="v1",
        insights=[],
    )
    monkeypatch.setattr(insights_service_module, "_today", lambda: dt.date(2026, 10, 2))

    assert (await insights_service.read(db_session, test_user.id)).status == "stale"


async def test_read_only_soft_deleted_rows_is_no_data(db_session, test_user, add):
    await add(test_user, "2026-09-05", "-200.00", deleted=True)

    assert (await insights_service.read(db_session, test_user.id)).status == "no_data"


async def test_generate_without_rows_does_not_call_the_model(db_session, test_user):
    patcher, mock = model()
    with patcher:
        response = await insights_service.generate(db_session, test_user.id)

    assert response.status == "no_data"
    mock.assert_not_awaited()


async def test_generate_failure_keeps_the_previous_set(db_session, test_user, add):
    await aged(add, test_user)
    patcher, _ = model()
    with patcher:
        await insights_service.generate(db_session, test_user.id)
    stored = await insight_repository.get(db_session, test_user.id)

    failing, _ = model(error=InvalidModelAnswer("ValidationError"))
    with failing, pytest.raises(InsightsUnavailableError):
        await insights_service.generate(db_session, test_user.id)

    after = await insight_repository.get(db_session, test_user.id)
    assert after.generated_at == stored.generated_at
    assert after.insights == stored.insights


async def test_generate_stores_zero_insights_as_fresh(db_session, test_user, add):
    await aged(add, test_user)
    patcher, _ = model(result=[])
    with patcher:
        generated = await insights_service.generate(db_session, test_user.id)

    assert generated.status == "fresh"
    assert generated.insights == []
    assert (await insights_service.read(db_session, test_user.id)).status == "fresh"
