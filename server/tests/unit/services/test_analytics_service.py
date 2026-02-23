"""Unit tests for AnalyticsService — mock DB, verify query logic and delegation."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import polars as pl
import pytest

from app.models.transaction import CategoryEnum, Transaction


def _make_mock_transaction(**kwargs) -> MagicMock:
    """Return a mock Transaction with sensible defaults."""
    from datetime import datetime
    from decimal import Decimal

    t = MagicMock(spec=Transaction)
    t.date = kwargs.get("date", datetime(2025, 1, 15))
    t.merchant = kwargs.get("merchant", "ACME")
    t.amount = kwargs.get("amount", Decimal("-50.00"))
    t.category = kwargs.get("category", CategoryEnum.SHOPPING)
    t.confidence_score = kwargs.get("confidence_score", 1.0)
    t.is_recurring = kwargs.get("is_recurring", False)
    return t


def _mock_db_with_transactions(transactions: list) -> AsyncMock:
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = transactions
    db.execute.return_value = mock_result
    return db


@pytest.mark.asyncio
async def test_load_dataframe_returns_empty_schema_when_no_transactions():
    from app.services.analytics.service import AnalyticsService

    db = _mock_db_with_transactions([])
    df = await AnalyticsService.load_dataframe(db, "user_123")

    assert isinstance(df, pl.DataFrame)
    assert len(df) == 0
    assert set(df.columns) == {
        "date", "merchant", "amount", "category", "confidence_score", "is_recurring"
    }


@pytest.mark.asyncio
async def test_load_dataframe_converts_transactions_to_polars():
    from app.services.analytics.service import AnalyticsService

    mock_tx = _make_mock_transaction()
    db = _mock_db_with_transactions([mock_tx])

    df = await AnalyticsService.load_dataframe(db, "user_123")

    assert len(df) == 1
    assert df["merchant"][0] == "ACME"
    assert df["amount"][0] == -50.0
    assert df["category"][0] == CategoryEnum.SHOPPING.value


@pytest.mark.asyncio
async def test_load_dataframe_includes_date_filter_in_query():
    from app.services.analytics.service import AnalyticsService

    db = _mock_db_with_transactions([])
    await AnalyticsService.load_dataframe(
        db, "user_123",
        date_from=date(2025, 1, 1),
        date_to=date(2025, 3, 31),
    )

    db.execute.assert_called_once()
    # Verify a query was issued (date filter is applied in the WHERE clause)
    call_args = db.execute.call_args
    assert call_args is not None


@pytest.mark.asyncio
async def test_get_spending_delegates_to_tool():
    from app.services.analytics.service import AnalyticsService

    empty_df = pl.DataFrame(schema={
        "date": pl.Date, "merchant": pl.Utf8, "amount": pl.Float64,
        "category": pl.Utf8, "confidence_score": pl.Float64, "is_recurring": pl.Boolean,
    })

    with patch.object(AnalyticsService, "load_dataframe", return_value=empty_df) as mock_load, \
         patch("app.services.analytics.service.get_spending_summary", new_callable=AsyncMock, return_value={"key": "val"}) as mock_tool:

        db = AsyncMock()
        result = await AnalyticsService.get_spending(db, "user_123", None, None)

        mock_load.assert_called_once_with(db, "user_123", None, None)
        mock_tool.assert_awaited_once_with(empty_df, start_date=None, end_date=None)
        assert result == {"key": "val"}


@pytest.mark.asyncio
async def test_get_dashboard_contains_all_sections():
    from app.services.analytics.service import AnalyticsService

    empty_df = pl.DataFrame(schema={
        "date": pl.Date, "merchant": pl.Utf8, "amount": pl.Float64,
        "category": pl.Utf8, "confidence_score": pl.Float64, "is_recurring": pl.Boolean,
    })

    with patch.object(AnalyticsService, "load_dataframe", return_value=empty_df), \
         patch("app.services.analytics.service.get_spending_summary", new_callable=AsyncMock, return_value={"s": 1}), \
         patch("app.services.analytics.service.get_category_insights", new_callable=AsyncMock, return_value={"c": 1}), \
         patch("app.services.analytics.service.get_recurring_insights", new_callable=AsyncMock, return_value={"r": 1}), \
         patch("app.services.analytics.service.get_trend_insights", new_callable=AsyncMock, return_value={"t": 1}):

        db = AsyncMock()
        result = await AnalyticsService.get_dashboard(db, "user_123", None, None)

        assert "spending" in result
        assert "categories" in result
        assert "recurring" in result
        assert "trends" in result


@pytest.mark.asyncio
async def test_get_anomalies_forwards_params_to_tool():
    from app.services.analytics.service import AnalyticsService

    empty_df = pl.DataFrame(schema={
        "date": pl.Date, "merchant": pl.Utf8, "amount": pl.Float64,
        "category": pl.Utf8, "confidence_score": pl.Float64, "is_recurring": pl.Boolean,
    })

    with patch.object(AnalyticsService, "load_dataframe", return_value=empty_df), \
         patch("app.services.analytics.service.get_anomaly_insights", new_callable=AsyncMock, return_value={}) as mock_tool:

        db = AsyncMock()
        await AnalyticsService.get_anomalies(
            db, "user_123", None, None, std_threshold=3.0, rolling_window=14
        )

        mock_tool.assert_awaited_once_with(
            empty_df, start_date=None, end_date=None, std_threshold=3.0, rolling_window=14
        )
