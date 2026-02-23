"""Unit tests for refactored financial tools — verify pl.DataFrame interface."""

from datetime import date
import polars as pl
import pytest


def _make_df() -> pl.DataFrame:
    """Minimal valid DataFrame matching the analytics module schema."""
    return pl.DataFrame({
        "date": [date(2025, 1, 15), date(2025, 1, 20), date(2025, 2, 10)],
        "merchant": ["ACME", "BurgerCo", "ACME"],
        "amount": [-50.0, -20.0, 200.0],
        "category": ["Shopping", "Food & Groceries", "Income"],
        "confidence_score": [1.0, 0.9, 1.0],
        "is_recurring": [False, False, False],
    })


def _make_income_only_df() -> pl.DataFrame:
    """DataFrame with only income transactions — no expenses to analyse."""
    return pl.DataFrame({
        "date": [date(2025, 1, 15)],
        "merchant": ["Employer"],
        "amount": [2000.0],
        "category": ["Income"],
        "confidence_score": [1.0],
        "is_recurring": [False],
    })


@pytest.mark.asyncio
async def test_get_spending_summary_accepts_dataframe():
    from app.tools.financial import get_spending_summary
    result = await get_spending_summary(_make_df())
    assert isinstance(result, dict)
    assert "overview" in result
    assert "recent_trend" in result


@pytest.mark.asyncio
async def test_get_category_insights_accepts_dataframe():
    from app.tools.financial import get_category_insights
    result = await get_category_insights(_make_df())
    assert isinstance(result, dict)
    assert "top_categories" in result


@pytest.mark.asyncio
async def test_get_recurring_insights_accepts_dataframe():
    from app.tools.financial import get_recurring_insights
    result = await get_recurring_insights(_make_df())
    assert isinstance(result, dict)
    assert "recurring_summary" in result


@pytest.mark.asyncio
async def test_get_trend_insights_accepts_dataframe():
    from app.tools.financial import get_trend_insights
    result = await get_trend_insights(_make_df())
    assert isinstance(result, dict)
    assert "monthly_trend" in result


@pytest.mark.asyncio
async def test_get_behavioral_patterns_accepts_dataframe():
    from app.tools.financial import get_behavioral_patterns
    result = await get_behavioral_patterns(_make_df())
    assert isinstance(result, dict)
    assert "day_of_week" in result


@pytest.mark.asyncio
async def test_get_anomaly_insights_accepts_dataframe():
    from app.tools.financial import get_anomaly_insights
    result = await get_anomaly_insights(_make_df())
    assert isinstance(result, dict)
    assert "insights" in result
    assert result["insights"]["detection_window_days"] == 30


@pytest.mark.asyncio
async def test_get_merchant_insights_accepts_dataframe():
    from app.tools.financial import get_merchant_insights
    result = await get_merchant_insights(_make_df())
    assert isinstance(result, dict)
    assert "top_merchants" in result
    assert "concentration_metrics" in result


@pytest.mark.asyncio
async def test_get_spending_stability_accepts_dataframe():
    from app.tools.financial import get_spending_stability_profile
    result = await get_spending_stability_profile(_make_df())
    assert isinstance(result, dict)
    assert "stability_distribution" in result


@pytest.mark.asyncio
async def test_get_anomaly_insights_forwards_std_threshold():
    from app.tools.financial import get_anomaly_insights
    result = await get_anomaly_insights(_make_df(), std_threshold=3.0, rolling_window=14)
    assert result["insights"]["threshold_std"] == 3.0
    assert result["insights"]["detection_window_days"] == 14


# ---------------------------------------------------------------------------
# Income-only edge case — no expenses means all expense-path analytics are empty
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_recurring_insights_income_only():
    """All-income input must not crash — recurring_summary returns an empty list."""
    from app.tools.financial import get_recurring_insights
    result = await get_recurring_insights(_make_income_only_df())
    assert isinstance(result, dict)
    assert result["monthly_recurring_costs"] == []
    assert result["recurring_summary"] == []


@pytest.mark.asyncio
async def test_get_category_insights_income_only():
    from app.tools.financial import get_category_insights
    result = await get_category_insights(_make_income_only_df())
    assert isinstance(result, dict)
    assert result["top_categories"] == []


@pytest.mark.asyncio
async def test_get_behavioral_patterns_income_only():
    from app.tools.financial import get_behavioral_patterns
    result = await get_behavioral_patterns(_make_income_only_df())
    assert isinstance(result, dict)
    assert result["day_of_week"]["by_weekday"] == []


@pytest.mark.asyncio
async def test_get_merchant_insights_income_only():
    from app.tools.financial import get_merchant_insights
    result = await get_merchant_insights(_make_income_only_df())
    assert isinstance(result, dict)
    assert result["top_merchants"] == []
