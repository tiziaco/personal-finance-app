"""Integration tests for GET /api/v1/analytics/* endpoints.

Full stack: router → AnalyticsService → DB → tools → response.
All writes are rolled back after each test (outer transaction pattern).
"""

import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration

BASE = "/api/v1/analytics"

ALL_ENDPOINTS = [
    f"{BASE}/dashboard",
    f"{BASE}/spending",
    f"{BASE}/categories",
    f"{BASE}/merchants",
    f"{BASE}/recurring",
    f"{BASE}/behavior",
    f"{BASE}/anomalies",
]


# ── Auth ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", ALL_ENDPOINTS)
@pytest.mark.asyncio
async def test_unauthenticated_returns_401(client, url):
    resp = await client.get(url)
    assert resp.status_code == 401


# ── Empty dataset (no transactions) ──────────────────────────────────────────

@pytest.mark.parametrize("url", ALL_ENDPOINTS)
@pytest.mark.asyncio
async def test_all_endpoints_return_200_with_no_transactions(authenticated_client, url):
    """User exists but has zero transactions — should never 500."""
    resp = await authenticated_client.get(url)
    assert resp.status_code == 200


# ── Dashboard ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_contains_all_sections(authenticated_client, transactions_400):
    resp = await authenticated_client.get(f"{BASE}/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert "spending" in body
    assert "categories" in body
    assert "recurring" in body
    assert "trends" in body
    assert "generated_at" in body


# ── Income-only dataset ───────────────────────────────────────────────────────

@pytest.mark.parametrize("url", ALL_ENDPOINTS)
@pytest.mark.asyncio
async def test_all_endpoints_return_200_with_income_only(
    authenticated_client, transactions_income_only, url
):
    """User has only income transactions — expense-path analytics must return empty,
    not crash with ColumnNotFoundError."""
    resp = await authenticated_client.get(url)
    assert resp.status_code == 200


# ── Single-domain endpoints ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_spending_returns_data_and_generated_at(authenticated_client, transactions_400):
    resp = await authenticated_client.get(f"{BASE}/spending")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "generated_at" in body


@pytest.mark.asyncio
async def test_categories_top_n_param(authenticated_client, transactions_10):
    resp = await authenticated_client.get(f"{BASE}/categories?top_n=3")
    assert resp.status_code == 200
    body = resp.json()
    top = body["data"].get("top_categories", [])
    assert len(top) <= 3


@pytest.mark.asyncio
async def test_merchants_returns_concentration_metrics(authenticated_client, transactions_2_months):
    resp = await authenticated_client.get(f"{BASE}/merchants")
    assert resp.status_code == 200
    body = resp.json()
    assert "concentration_metrics" in body["data"]


@pytest.mark.asyncio
async def test_recurring_returns_hidden_subscriptions_key(authenticated_client, transactions_400):
    resp = await authenticated_client.get(f"{BASE}/recurring")
    assert resp.status_code == 200
    body = resp.json()
    assert "recurring" in body["data"]
    assert "hidden_subscriptions" in body["data"]["recurring"]


@pytest.mark.asyncio
async def test_behavior_returns_expected_sections(authenticated_client, transactions_400):
    resp = await authenticated_client.get(f"{BASE}/behavior")
    assert resp.status_code == 200
    body = resp.json()
    assert "day_of_week" in body["data"]
    assert "seasonality" in body["data"]
    assert "volatility" in body["data"]


@pytest.mark.asyncio
async def test_anomalies_params_forwarded(authenticated_client, transactions_400):
    resp = await authenticated_client.get(
        f"{BASE}/anomalies?std_threshold=3.0&rolling_window=14"
    )
    assert resp.status_code == 200
    body = resp.json()
    insights = body["data"].get("insights", {})
    assert insights.get("threshold_std") == 3.0
    assert insights.get("detection_window_days") == 14


# ── Date filter ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_spending_date_filter_restricts_data(authenticated_client, transactions_400):
    resp = await authenticated_client.get(
        f"{BASE}/spending?date_from=2025-01-01&date_to=2025-03-31"
    )
    assert resp.status_code == 200
    body = resp.json()
    date_range = body["data"].get("date_range", {})
    if date_range.get("start"):
        assert date_range["start"] >= "2025-01-01"
    if date_range.get("end"):
        assert date_range["end"] <= "2025-03-31"


# ── Edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", ALL_ENDPOINTS)
@pytest.mark.asyncio
async def test_single_transaction_does_not_500(authenticated_client, transactions_single, url):
    """Edge case: division-by-zero guards, empty trend functions."""
    resp = await authenticated_client.get(url)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_behavior_with_same_month_data_does_not_500(
    authenticated_client, transactions_10
):
    """Edge case: seasonality decomposition needs multiple months — must not crash."""
    resp = await authenticated_client.get(f"{BASE}/behavior")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_anomalies_with_thin_rolling_window(authenticated_client, transactions_2_months):
    """Edge case: 2-month window is thin for a 30-day rolling average."""
    resp = await authenticated_client.get(f"{BASE}/anomalies")
    assert resp.status_code == 200
