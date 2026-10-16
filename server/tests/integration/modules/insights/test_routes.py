"""The insights routes: auth, the 503, ownership, and that GET never calls the model."""

import datetime as dt
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.insights import WrittenInsight
from app.agents.shared.structured import InvalidModelAnswer
from app.integrations.llm import LLMServiceError
from app.modules.analytics import service as analytics_service_module
from app.modules.insights.repository import insight_repository

pytestmark = pytest.mark.integration

BASE = "/api/v1/insights"
LONG_AGO = dt.datetime(2026, 9, 1, tzinfo=dt.UTC)


@pytest.fixture(autouse=True)
def today(monkeypatch):
    monkeypatch.setattr(analytics_service_module, "_today", lambda: dt.date(2026, 10, 16))


def _written():
    return [
        WrittenInsight(
            section="savings",
            severity="info",
            period="month",
            summary="s",
            narrative="n",
            key_figure=None,
            link=None,
        )
    ]


async def test_signed_out_is_401(client):
    assert (await client.get(BASE)).status_code == 401
    assert (await client.post(f"{BASE}/generate")).status_code == 401


async def test_get_never_calls_the_model(authenticated_client, test_user, add):
    txn = await add(test_user, "2026-09-05", "-200.00")
    txn.updated_at = LONG_AGO
    with patch("app.modules.insights.service.write_insights", AsyncMock()) as mock:
        response = await authenticated_client.get(BASE)

    assert response.status_code == 200
    assert response.json()["status"] == "none"
    mock.assert_not_awaited()


async def test_generate_then_get(authenticated_client, test_user, add):
    txn = await add(test_user, "2026-09-05", "-200.00")
    txn.updated_at = LONG_AGO
    with patch("app.modules.insights.service.write_insights", AsyncMock(return_value=_written())):
        generated = await authenticated_client.post(f"{BASE}/generate")
    fetched = await authenticated_client.get(BASE)

    assert generated.status_code == 200
    assert fetched.json() == generated.json()
    assert fetched.json()["status"] == "fresh"
    assert fetched.json()["insights"][0]["summary"] == "s"


@pytest.mark.parametrize("error", [InvalidModelAnswer("ValidationError"), LLMServiceError("down")])
async def test_generate_failure_keeps_the_previous_set_and_is_503(authenticated_client, test_user, add, error):
    txn = await add(test_user, "2026-09-05", "-200.00")
    txn.updated_at = LONG_AGO
    with patch("app.modules.insights.service.write_insights", AsyncMock(return_value=_written())):
        await authenticated_client.post(f"{BASE}/generate")
    before = (await authenticated_client.get(BASE)).json()

    with patch("app.modules.insights.service.write_insights", AsyncMock(side_effect=error)):
        response = await authenticated_client.post(f"{BASE}/generate")

    assert response.status_code == 503
    assert response.json()["error"] == "INSIGHTS_UNAVAILABLE"
    assert (await authenticated_client.get(BASE)).json() == before


async def test_another_users_set_is_not_returned(authenticated_client, test_user, other_user, add, db_session):
    txn = await add(test_user, "2026-09-05", "-200.00")
    txn.updated_at = LONG_AGO
    await insight_repository.replace(
        db_session,
        other_user.id,
        generated_at=dt.datetime.now(dt.UTC),
        reference_month="2026-09",
        baseline_months=1,
        month_to_date_through=None,
        prompt_version="v1",
        insights=[],
    )

    response = await authenticated_client.get(BASE)

    assert response.json()["status"] == "none"
