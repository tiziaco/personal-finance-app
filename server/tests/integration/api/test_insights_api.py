"""Integration tests for GET /api/v1/insights."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.integration


# ── Auth ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_insights_unauthenticated(client):
    response = await client.get("/api/v1/insights")
    assert response.status_code == 401


# ── Happy path ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_insights_no_transactions_returns_empty(authenticated_client):
    """User with no transactions gets 200 with empty insights list."""
    with patch(
        "app.services.insights.service.generate_insights",
        new_callable=AsyncMock,
        return_value={"formatted_insights": [], "errors": []},
    ):
        response = await authenticated_client.get("/api/v1/insights")

    assert response.status_code == 200
    data = response.json()
    assert data["insights"] == []
    assert "generated_at" in data


@pytest.mark.asyncio
async def test_get_insights_with_transactions_returns_populated(
    authenticated_client, transactions_400
):
    """With 400 transactions, insights list is non-empty."""
    mock_insight = MagicMock()
    mock_insight.model_dump.return_value = {
        "insight_id": "top_spending_category",
        "type": "spending_behavior",
        "severity": "info",
        "time_window": "last_period",
        "summary": "Your top spending category is Bars & Restaurants.",
        "narrative_analysis": None,
        "supporting_metrics": {"category": "Bars & Restaurants", "percentage": 28.5},
        "confidence": 0.95,
        "section": "spending",
    }

    with patch(
        "app.services.insights.service.generate_insights",
        new_callable=AsyncMock,
        return_value={"formatted_insights": [mock_insight], "errors": []},
    ):
        response = await authenticated_client.get("/api/v1/insights")

    assert response.status_code == 200
    data = response.json()
    assert len(data["insights"]) == 1
    assert data["insights"][0]["insight_id"] == "top_spending_category"
    assert data["insights"][0]["section"] == "spending"
    assert "generated_at" in data


# ── Cache behaviour ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_insights_serves_cached_row(
    authenticated_client, db_session, test_user
):
    """Second call serves cached row — generate_insights is never called."""
    from app.models.insight import Insight as InsightModel

    cached = InsightModel(
        user_id=test_user.id,
        insights=[
            {
                "insight_id": "cached_insight",
                "type": "trend",
                "severity": "medium",
                "time_window": "last_3_months",
                "summary": "Spending increased by 12%.",
                "narrative_analysis": None,
                "supporting_metrics": {"mom_growth": 0.12},
                "confidence": 0.88,
                "section": "trends",
            }
        ],
        generated_at=datetime.now(UTC),
    )
    db_session.add(cached)
    await db_session.flush()

    with patch(
        "app.services.insights.service.generate_insights",
        new_callable=AsyncMock,
    ) as mock_gen:
        response = await authenticated_client.get("/api/v1/insights")
        mock_gen.assert_not_awaited()

    assert response.status_code == 200
    data = response.json()
    assert data["insights"][0]["insight_id"] == "cached_insight"


# ── LLM enrichment disabled in tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_insights_narrative_analysis_null_when_llm_disabled(
    authenticated_client, transactions_10
):
    """When LLM enrichment is disabled, narrative_analysis is null."""
    mock_insight = MagicMock()
    mock_insight.model_dump.return_value = {
        "insight_id": "subscription_load_index",
        "type": "recurring_subscriptions",
        "severity": "info",
        "time_window": "monthly",
        "summary": "Recurring expenses account for 15% of spending.",
        "narrative_analysis": None,   # LLM disabled → null
        "supporting_metrics": {"percentage": 15.0},
        "confidence": 0.85,
        "section": "subscriptions",
    }

    with patch(
        "app.services.insights.service.generate_insights",
        new_callable=AsyncMock,
        return_value={"formatted_insights": [mock_insight], "errors": []},
    ):
        response = await authenticated_client.get("/api/v1/insights")

    assert response.status_code == 200
    data = response.json()
    assert data["insights"][0]["narrative_analysis"] is None


# ── Response schema validation ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_insights_response_has_correct_schema(authenticated_client):
    """Response envelope has `insights` list and `generated_at` datetime."""
    with patch(
        "app.services.insights.service.generate_insights",
        new_callable=AsyncMock,
        return_value={"formatted_insights": [], "errors": []},
    ):
        response = await authenticated_client.get("/api/v1/insights")

    assert response.status_code == 200
    data = response.json()
    assert "insights" in data
    assert "generated_at" in data
    assert isinstance(data["insights"], list)
