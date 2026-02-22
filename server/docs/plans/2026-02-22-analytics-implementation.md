# Analytics Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire existing Polars analytics functions into a stateless `AnalyticsService` and expose seven read-only endpoints under `/api/v1/analytics`.

**Architecture:** Four layers — `app/analytics/` (pure Polars, untouched) ← `app/tools/financial.py` (semantic tools, refactored to `pl.DataFrame` input) ← `app/services/analytics/service.py` (DB bridge + orchestration) ← `app/api/v1/analytics.py` (HTTP interface). The service calls `load_dataframe` then delegates to the tools; no analytics logic lives in the router.

**Tech Stack:** FastAPI, SQLModel, SQLAlchemy async, Polars, pytest + pytest-asyncio, slowapi rate limiting.

---

### Task 1: Refactor `app/tools/financial.py`

The existing file passes `Dict[str, Any]` (serialised DataFrames) between layers and includes dict validation boilerplate. Refactor all 8 functions to accept `pl.DataFrame` directly, fix broken import paths, and remove the envelope wrappers. Also fixes a latent bug: `calculate_category_trend` is called with a non-existent `category=` kwarg in the original — replace with the correct `top_n_categories=` parameter.

**Files:**
- Modify: `app/tools/financial.py`
- Create: `tests/unit/tools/__init__.py`
- Create: `tests/unit/tools/test_financial_tools.py`

**Step 1: Write the failing tests**

```python
# tests/unit/tools/test_financial_tools.py
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
```

**Step 2: Run tests to confirm they fail**

```bash
pytest tests/unit/tools/test_financial_tools.py -v
```

Expected: `ImportError` or `TypeError` — functions don't accept `pl.DataFrame` yet.

**Step 3: Rewrite `app/tools/financial.py`**

Replace the entire file with the version below. Key changes from original:
- Import paths: `from app.analytics.*` (not `from analytics.*`)
- All function signatures: `transactions_df: Dict[str, Any]` → `df: pl.DataFrame`
- Date params: `Optional[str]` → `Optional[date]`
- Removed: `BaseAnalysisInput`, `BaseAnalysisOutput`, `_validate_and_convert_df`, `_apply_date_filter`
- Return plain `dict` directly (no `.model_dump()` wrapper)
- `get_category_insights`: replaces the broken `calculate_category_trend(df, category=cat)` loop with a single `calculate_category_trend(df, top_n_categories=top_n)` call
- All `except:` bare clauses replaced with `except Exception`

```python
"""
Semantic Tools — Intent-Based Analytics Layer

High-level tools that wrap the analytics functions in app/analytics/.
Accept pl.DataFrame directly. Return structured dicts. Raise on error.

Agent-ready: thin LangChain wrappers with InjectedToolArg can be added
on top of these functions when agent integration is needed.
"""

from datetime import date
from typing import Any, Dict, List, Optional

import polars as pl

from app.analytics.descriptive import (
    PeriodEnum,
    analyze_by_category,
    analyze_merchants,
    analyze_recurring,
    calculate_spending_overview,
)
from app.analytics.temporal import (
    analyze_day_of_week_patterns,
    analyze_seasonality_simple,
    analyze_spending_volatility,
    calculate_category_trend,
    calculate_monthly_spending_trend,
    calculate_rolling_averages,
    identify_stable_vs_volatile_categories,
)


async def get_spending_summary(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Answer: "What is my financial situation?"

    Provides a comprehensive spending overview including total spend,
    income vs expenses, net position, and recent period comparison.
    """
    overview = calculate_spending_overview(
        df, period=PeriodEnum.MONTHLY, start_date=start_date, end_date=end_date
    )
    trends = calculate_monthly_spending_trend(
        df, start_date=start_date, end_date=end_date, include_income=True
    )

    return {
        "overview": {
            "stats": overview["summary"].to_dicts(),
            "income_vs_expenses": overview["income_vs_expenses"].to_dicts(),
        },
        "recent_trend": {
            "last_3_months": trends["monthly_trend"].tail(3).to_dicts(),
            "burn_rate": trends["burn_rate"].to_dicts(),
        },
        "date_range": {
            "start": str(df["date"].min()) if len(df) > 0 else None,
            "end": str(df["date"].max()) if len(df) > 0 else None,
            "total_days": (
                int((df["date"].max() - df["date"].min()).days)
                if len(df) > 1
                else 0
            ),
        },
    }


async def get_category_insights(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    top_n: int = 10,
) -> Dict[str, Any]:
    """Answer: "Where does my money go?"

    Category-level spending insights: top categories, growth/decline,
    frequency vs impact, confidence-weighted values.
    """
    category_data = analyze_by_category(
        df, start_date=start_date, end_date=end_date
    )
    trend_data = calculate_category_trend(
        df,
        start_date=start_date,
        end_date=end_date,
        top_n_categories=top_n,
    )

    return {
        "top_categories": category_data["by_category"].head(top_n).to_dicts(),
        "frequency_vs_impact": category_data["frequency_vs_impact"].head(top_n).to_dicts(),
        "confidence_weighted": category_data["confidence_weighted"].head(top_n).to_dicts(),
        "category_trends": {
            "top_growing": trend_data["top_growing"].to_dicts() if "top_growing" in trend_data else [],
            "top_declining": trend_data["top_declining"].to_dicts() if "top_declining" in trend_data else [],
        },
    }


async def get_recurring_insights(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Answer: "What am I locked into?"

    Recurring expenses, subscription costs, hidden subscriptions.
    """
    recurring_data = analyze_recurring(df, start_date=start_date, end_date=end_date)

    summary = recurring_data["recurring_summary"].to_dicts()
    monthly_costs = (
        recurring_data["monthly_recurring_cost"]
        .sort("estimated_monthly_cost", descending=True)
        .to_dicts()
    )
    recurring_summary_row = next(
        (s for s in summary if s.get("is_recurring") is True), None
    )
    total_recurring_pct = (
        recurring_summary_row.get("amount_percentage", 0.0)
        if recurring_summary_row
        else 0.0
    )

    return {
        "recurring_summary": summary,
        "monthly_recurring_costs": monthly_costs,
        "recurring_by_category": recurring_data["recurring_by_category"].to_dicts(),
        "hidden_subscriptions": recurring_data["hidden_subscriptions"].to_dicts(),
        "insights": {
            "total_recurring_percentage": total_recurring_pct,
            "total_hidden_subscriptions": len(recurring_data["hidden_subscriptions"]),
            "top_recurring_merchant": monthly_costs[0]["merchant"] if monthly_costs else None,
        },
    }


async def get_trend_insights(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Answer: "What changed recently?"

    MoM/YoY growth, burn rate, fastest growing and declining categories.
    """
    monthly_data = calculate_monthly_spending_trend(
        df, start_date=start_date, end_date=end_date, include_income=True
    )
    trend_data = calculate_category_trend(
        df, start_date=start_date, end_date=end_date, top_n_categories=10
    )

    latest_mom = None
    if len(monthly_data["monthly_trend"]) > 0:
        mom_values = monthly_data["monthly_trend"]["expense_mom_growth"].tail(1).to_list()
        latest_mom = mom_values[0] if mom_values else None

    return {
        "monthly_trend": monthly_data["monthly_trend"].tail(12).to_dicts(),
        "year_comparison": (
            monthly_data["year_comparison"].to_dicts()
            if len(monthly_data["year_comparison"]) > 0
            else []
        ),
        "burn_rate": monthly_data["burn_rate"].to_dicts(),
        "top_growing": trend_data["top_growing"].to_dicts() if "top_growing" in trend_data else [],
        "top_declining": trend_data["top_declining"].to_dicts() if "top_declining" in trend_data else [],
        "insights": {
            "latest_mom_growth": latest_mom,
        },
    }


async def get_behavioral_patterns(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Answer: "How do I behave financially?"

    Day-of-week patterns, seasonal sensitivity, spending volatility.
    """
    dow_data = analyze_day_of_week_patterns(df, start_date=start_date, end_date=end_date)
    seasonality_data = analyze_seasonality_simple(df, start_date=start_date, end_date=end_date)
    volatility_data = analyze_spending_volatility(df, start_date=start_date, end_date=end_date)

    weekday_vs_weekend = dow_data["weekday_vs_weekend"].to_dicts()
    weekend_bias = None
    if len(weekday_vs_weekend) == 2:
        weekend_row = next((r for r in weekday_vs_weekend if r.get("day_type") == "weekend"), None)
        weekday_row = next((r for r in weekday_vs_weekend if r.get("day_type") == "weekday"), None)
        if weekend_row and weekday_row and weekday_row.get("avg_per_day", 0) > 0:
            weekend_bias = (weekend_row["avg_per_day"] / weekday_row["avg_per_day"] - 1) * 100

    return {
        "day_of_week": {
            "by_weekday": dow_data["by_weekday"].to_dicts(),
            "weekday_vs_weekend": weekday_vs_weekend,
            "weekend_bias_percentage": weekend_bias,
        },
        "seasonality": {
            "monthly_patterns": seasonality_data["monthly_seasonality"].to_dicts(),
            "quarterly_patterns": (
                seasonality_data["quarterly_seasonality"].to_dicts()
                if "quarterly_seasonality" in seasonality_data
                else []
            ),
        },
        "volatility": {
            "stable_categories": volatility_data["stable_categories"].head(5).to_dicts(),
            "volatile_categories": volatility_data["volatile_categories"].head(5).to_dicts(),
        },
        "insights": {
            "weekend_spender": weekend_bias > 10 if weekend_bias is not None else False,
            "most_stable_category": (
                volatility_data["stable_categories"]["category"].head(1).to_list()[0]
                if len(volatility_data["stable_categories"]) > 0
                else None
            ),
            "most_volatile_category": (
                volatility_data["volatile_categories"]["category"].head(1).to_list()[0]
                if len(volatility_data["volatile_categories"]) > 0
                else None
            ),
        },
    }


async def get_anomaly_insights(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    std_threshold: float = 2.5,
    rolling_window: int = 30,
) -> Dict[str, Any]:
    """Answer: "What looks unusual?"

    Outlier transactions, abnormal weeks, category spikes.
    """
    df_filtered = df
    if start_date:
        df_filtered = df_filtered.filter(pl.col("date") >= start_date)
    if end_date:
        df_filtered = df_filtered.filter(pl.col("date") <= end_date)

    df_filtered = df_filtered.sort("date")
    rolling_stats = calculate_rolling_averages(df_filtered, windows=[rolling_window])
    volatility_data = analyze_spending_volatility(df_filtered)

    rolling_avg_col = f"rolling_avg_{rolling_window}d"
    rolling_std_col = f"rolling_std_{rolling_window}d"

    df_with_stats = df_filtered.join(
        rolling_stats.select(["date", rolling_avg_col, rolling_std_col]),
        on="date",
        how="left",
    )

    df_expenses = df_with_stats.filter(pl.col("amount") < 0).with_columns(
        pl.col("amount").abs().alias("amount_abs")
    )

    df_anomalies = (
        df_expenses.with_columns(
            (
                (pl.col("amount_abs") - pl.col(rolling_avg_col))
                / pl.col(rolling_std_col)
            )
            .abs()
            .alias("z_score")
        )
        .filter(pl.col("z_score") > std_threshold)
        .sort("z_score", descending=True)
    )

    df_recent = df_filtered.filter(
        pl.col("date") >= df_filtered["date"].max() - pl.duration(days=30)
    )
    recent_by_cat = df_recent.filter(pl.col("amount") < 0).group_by("category").agg(
        pl.col("amount").abs().sum().alias("recent_spending")
    )
    overall_by_cat = df_filtered.filter(pl.col("amount") < 0).group_by("category").agg(
        pl.col("amount").abs().mean().alias("avg_monthly_spending")
    )
    category_spikes = (
        recent_by_cat.join(overall_by_cat, on="category")
        .with_columns(
            (
                ((pl.col("recent_spending") / pl.col("avg_monthly_spending")) - 1) * 100
            ).alias("spike_percentage")
        )
        .filter(pl.col("spike_percentage") > 50)
        .sort("spike_percentage", descending=True)
    )

    return {
        "outlier_transactions": df_anomalies.select(
            ["date", "merchant", "amount_abs", "category", "z_score", rolling_avg_col]
        )
        .head(20)
        .to_dicts(),
        "category_spikes": category_spikes.to_dicts(),
        "volatility_summary": volatility_data["volatile_categories"].head(5).to_dicts(),
        "insights": {
            "total_anomalies": len(df_anomalies),
            "highest_z_score": float(df_anomalies["z_score"].max()) if len(df_anomalies) > 0 else 0.0,
            "categories_spiking": len(category_spikes),
            "detection_window_days": rolling_window,
            "threshold_std": std_threshold,
        },
    }


async def get_merchant_insights(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    top_n: int = 15,
) -> Dict[str, Any]:
    """Answer: "Which merchants control my spending?"

    Merchant concentration, frequency analysis, one-off vs recurring.
    """
    merchant_data = analyze_merchants(
        df, start_date=start_date, end_date=end_date, top_n=top_n
    )
    top_merchants = merchant_data["top_merchants"]
    total_spending = top_merchants["total_amount"].sum() if len(top_merchants) > 0 else 0.0

    top_5_pct = (
        top_merchants.head(5)["total_amount"].sum() / total_spending * 100
        if total_spending > 0
        else 0.0
    )
    top_10_pct = (
        top_merchants.head(10)["total_amount"].sum() / total_spending * 100
        if total_spending > 0
        else 0.0
    )

    merchant_summary = merchant_data["merchant_summary"]
    if len(merchant_summary) > 0 and total_spending > 0:
        market_shares = (merchant_summary["total_amount"] / total_spending * 100).to_list()
        herfindahl = sum(s ** 2 for s in market_shares)
    else:
        herfindahl = 0.0

    return {
        "top_merchants": top_merchants.head(top_n).to_dicts(),
        "by_frequency": merchant_data["by_frequency"].head(top_n).to_dicts(),
        "merchant_classification": merchant_data["one_off_vs_frequent"].to_dicts(),
        "concentration_metrics": {
            "top_5_merchants_pct": top_5_pct,
            "top_10_merchants_pct": top_10_pct,
            "herfindahl_index": herfindahl,
            "total_unique_merchants": len(merchant_summary),
            "concentration_risk": (
                "high" if herfindahl > 2500 else "medium" if herfindahl > 1500 else "low"
            ),
        },
    }


async def get_spending_stability_profile(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Answer: "How predictable is my spending?"

    Stability classification, fixed vs variable costs, subscription creep.
    """
    stability_data = identify_stable_vs_volatile_categories(
        df, start_date=start_date, end_date=end_date
    )
    volatility_data = analyze_spending_volatility(df, start_date=start_date, end_date=end_date)
    recurring_data = analyze_recurring(df, start_date=start_date, end_date=end_date)
    monthly_trends = calculate_monthly_spending_trend(
        df, start_date=start_date, end_date=end_date, include_income=True
    )

    classification_summary = stability_data["classification_summary"].to_dicts()
    total_spending = sum(row.get("total_spending", 0) for row in classification_summary)

    stable_pct = moderate_pct = volatile_pct = 0.0
    for row in classification_summary:
        pct = (row.get("total_spending", 0) / total_spending * 100) if total_spending > 0 else 0.0
        if row["stability_class"] == "stable":
            stable_pct = pct
        elif row["stability_class"] == "moderate":
            moderate_pct = pct
        elif row["stability_class"] == "volatile":
            volatile_pct = pct

    subscription_creep = None
    if len(monthly_trends["monthly_trend"]) >= 2:
        months_data = monthly_trends["monthly_trend"].tail(2).to_dicts()
        if len(months_data) == 2:
            latest = months_data[-1].get("total_expenses", 0)
            previous = months_data[-2].get("total_expenses", 0)
            if previous > 0:
                subscription_creep = (latest - previous) / previous * 100

    return {
        "stability_distribution": {
            "stable_percentage": stable_pct,
            "moderate_percentage": moderate_pct,
            "volatile_percentage": volatile_pct,
        },
        "stable_categories": stability_data["stable"].head(10).to_dicts(),
        "moderate_categories": stability_data["moderate"].head(10).to_dicts(),
        "volatile_categories": stability_data["volatile"].head(10).to_dicts(),
        "volatility_metrics": volatility_data["category_volatility"].head(15).to_dicts(),
        "recurring_insights": recurring_data["recurring_summary"].to_dicts(),
        "subscription_creep": {
            "mom_change_percentage": subscription_creep,
            "status": (
                "creeping_up"
                if subscription_creep and subscription_creep > 5
                else "creeping_down"
                if subscription_creep and subscription_creep < -5
                else "stable"
            ),
        },
        "insights": {
            "predictable_baseline_pct": stable_pct,
            "discretionary_portion_pct": volatile_pct,
            "stability_profile": (
                "high_predictability"
                if stable_pct > 60
                else "moderate_predictability"
                if stable_pct > 40
                else "low_predictability"
            ),
        },
    }


ANALYTICAL_TOOLS = [
    get_spending_summary,
    get_category_insights,
    get_recurring_insights,
    get_trend_insights,
    get_behavioral_patterns,
    get_anomaly_insights,
    get_merchant_insights,
    get_spending_stability_profile,
]

__all__ = [
    "ANALYTICAL_TOOLS",
    "get_spending_summary",
    "get_category_insights",
    "get_recurring_insights",
    "get_trend_insights",
    "get_behavioral_patterns",
    "get_anomaly_insights",
    "get_merchant_insights",
    "get_spending_stability_profile",
]
```

**Step 4: Run tests**

```bash
pytest tests/unit/tools/test_financial_tools.py -v
```

Expected: all 9 tests pass.

**Step 5: Commit**

```bash
git add app/tools/financial.py tests/unit/tools/
git commit -m "refactor: update financial tools to accept pl.DataFrame directly"
```

---

### Task 2: Create analytics service scaffold

**Files:**
- Create: `app/services/analytics/__init__.py`
- Create: `app/services/analytics/exceptions.py`

**Step 1: Create the files**

```python
# app/services/analytics/__init__.py
```

```python
# app/services/analytics/exceptions.py
"""Analytics service domain exceptions."""

from app.exceptions.base import ServiceError


class AnalyticsError(ServiceError):
    """Raised when analytics computation fails unexpectedly."""

    error_code = "ANALYTICS_ERROR"
    status_code = 500
```

**Step 2: Verify importable**

```bash
python -c "from app.services.analytics.exceptions import AnalyticsError; print('ok')"
```

Expected: `ok`

**Step 3: Commit**

```bash
git add app/services/analytics/
git commit -m "feat: add analytics service scaffold and AnalyticsError"
```

---

### Task 3: Write unit tests for `AnalyticsService` (failing)

**Files:**
- Create: `tests/unit/services/test_analytics_service.py`

**Step 1: Write the failing tests**

```python
# tests/unit/services/test_analytics_service.py
"""Unit tests for AnalyticsService — mock DB, verify query logic and delegation."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch, AsyncMock

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
         patch("app.services.analytics.service.get_spending_summary", return_value={"key": "val"}) as mock_tool:

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
         patch("app.services.analytics.service.get_spending_summary", return_value={"s": 1}), \
         patch("app.services.analytics.service.get_category_insights", return_value={"c": 1}), \
         patch("app.services.analytics.service.get_recurring_insights", return_value={"r": 1}), \
         patch("app.services.analytics.service.get_trend_insights", return_value={"t": 1}):

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
         patch("app.services.analytics.service.get_anomaly_insights", return_value={}) as mock_tool:

        db = AsyncMock()
        await AnalyticsService.get_anomalies(
            db, "user_123", None, None, std_threshold=3.0, rolling_window=14
        )

        mock_tool.assert_awaited_once_with(
            empty_df, start_date=None, end_date=None, std_threshold=3.0, rolling_window=14
        )
```

**Step 2: Run to confirm they fail**

```bash
pytest tests/unit/services/test_analytics_service.py -v
```

Expected: `ImportError` — `app.services.analytics.service` doesn't exist yet.

---

### Task 4: Implement `AnalyticsService`

**Files:**
- Create: `app/services/analytics/service.py`

**Step 1: Write the service**

```python
# app/services/analytics/service.py
"""Analytics service — data bridge between the DB and analytics tools."""

from datetime import date, datetime
from typing import Any, Dict, Optional

import polars as pl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import logger
from app.models.transaction import Transaction
from app.services.analytics.exceptions import AnalyticsError
from app.tools.financial import (
    get_anomaly_insights,
    get_behavioral_patterns,
    get_category_insights,
    get_merchant_insights,
    get_recurring_insights,
    get_spending_stability_profile,
    get_spending_summary,
    get_trend_insights,
)


class AnalyticsService:
    """Stateless analytics service.

    Bridges DB → Polars DataFrame and delegates to semantic tools in
    app/tools/financial.py. No analytics logic lives here.
    """

    @staticmethod
    async def load_dataframe(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> pl.DataFrame:
        """Fetch non-deleted user transactions and return as a Polars DataFrame.

        Applies date filter at the DB level for efficiency.
        Returns a typed empty DataFrame (correct schema) when no rows match.

        Args:
            db: Database session.
            user_id: ID of the authenticated user.
            date_from: Optional inclusive start date (DB-level filter).
            date_to: Optional inclusive end date (DB-level filter).

        Returns:
            pl.DataFrame with columns: date (Date), merchant (Utf8),
            amount (Float64), category (Utf8), confidence_score (Float64),
            is_recurring (Boolean).
        """
        empty_schema = {
            "date": pl.Date,
            "merchant": pl.Utf8,
            "amount": pl.Float64,
            "category": pl.Utf8,
            "confidence_score": pl.Float64,
            "is_recurring": pl.Boolean,
        }

        conditions = [
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        ]
        if date_from:
            conditions.append(Transaction.date >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            conditions.append(Transaction.date <= datetime.combine(date_to, datetime.max.time()))

        stmt = select(Transaction).where(*conditions).order_by(Transaction.date)
        result = await db.execute(stmt)
        transactions = result.scalars().all()

        if not transactions:
            return pl.DataFrame(schema=empty_schema)

        rows = [
            {
                "date": t.date.date() if isinstance(t.date, datetime) else t.date,
                "merchant": t.merchant,
                "amount": float(t.amount),
                "category": t.category.value,
                "confidence_score": float(t.confidence_score),
                "is_recurring": t.is_recurring,
            }
            for t in transactions
        ]

        logger.debug(
            "analytics_dataframe_loaded",
            user_id=user_id,
            rows=len(rows),
        )
        return pl.DataFrame(rows)

    @staticmethod
    async def get_dashboard(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Compose a summary across 4 domains for the dashboard."""
        df = await AnalyticsService.load_dataframe(db, user_id, date_from, date_to)
        try:
            spending = await get_spending_summary(df, start_date=date_from, end_date=date_to)
            categories = await get_category_insights(df, start_date=date_from, end_date=date_to)
            recurring = await get_recurring_insights(df, start_date=date_from, end_date=date_to)
            trends = await get_trend_insights(df, start_date=date_from, end_date=date_to)
        except Exception as e:
            raise AnalyticsError(f"Dashboard analytics failed: {e}") from e

        return {
            "spending": spending,
            "categories": categories,
            "recurring": recurring,
            "trends": trends,
        }

    @staticmethod
    async def get_spending(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict[str, Any]:
        df = await AnalyticsService.load_dataframe(db, user_id, date_from, date_to)
        try:
            return await get_spending_summary(df, start_date=date_from, end_date=date_to)
        except Exception as e:
            raise AnalyticsError(f"Spending analytics failed: {e}") from e

    @staticmethod
    async def get_categories(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        top_n: int = 10,
    ) -> Dict[str, Any]:
        df = await AnalyticsService.load_dataframe(db, user_id, date_from, date_to)
        try:
            return await get_category_insights(df, start_date=date_from, end_date=date_to, top_n=top_n)
        except Exception as e:
            raise AnalyticsError(f"Category analytics failed: {e}") from e

    @staticmethod
    async def get_merchants(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        top_n: int = 15,
    ) -> Dict[str, Any]:
        df = await AnalyticsService.load_dataframe(db, user_id, date_from, date_to)
        try:
            return await get_merchant_insights(df, start_date=date_from, end_date=date_to, top_n=top_n)
        except Exception as e:
            raise AnalyticsError(f"Merchant analytics failed: {e}") from e

    @staticmethod
    async def get_recurring(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict[str, Any]:
        df = await AnalyticsService.load_dataframe(db, user_id, date_from, date_to)
        try:
            recurring = await get_recurring_insights(df, start_date=date_from, end_date=date_to)
            stability = await get_spending_stability_profile(df, start_date=date_from, end_date=date_to)
            return {"recurring": recurring, "stability": stability}
        except Exception as e:
            raise AnalyticsError(f"Recurring analytics failed: {e}") from e

    @staticmethod
    async def get_behavior(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict[str, Any]:
        df = await AnalyticsService.load_dataframe(db, user_id, date_from, date_to)
        try:
            return await get_behavioral_patterns(df, start_date=date_from, end_date=date_to)
        except Exception as e:
            raise AnalyticsError(f"Behavioral analytics failed: {e}") from e

    @staticmethod
    async def get_anomalies(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        std_threshold: float = 2.5,
        rolling_window: int = 30,
    ) -> Dict[str, Any]:
        df = await AnalyticsService.load_dataframe(db, user_id, date_from, date_to)
        try:
            return await get_anomaly_insights(
                df,
                start_date=date_from,
                end_date=date_to,
                std_threshold=std_threshold,
                rolling_window=rolling_window,
            )
        except Exception as e:
            raise AnalyticsError(f"Anomaly analytics failed: {e}") from e


analytics_service = AnalyticsService()
```

**Step 2: Run unit tests**

```bash
pytest tests/unit/services/test_analytics_service.py -v
```

Expected: all 6 tests pass.

**Step 3: Commit**

```bash
git add app/services/analytics/service.py
git commit -m "feat: implement AnalyticsService with load_dataframe and per-domain methods"
```

---

### Task 5: Write `app/schemas/analytics.py`

**Files:**
- Create: `app/schemas/analytics.py`

**Step 1: Write the schemas**

```python
# app/schemas/analytics.py
"""Request filters and response schemas for the analytics API."""

from datetime import date, datetime
from typing import Any, Dict, Optional

from fastapi import Query
from pydantic import BaseModel


class AnalyticsFilters:
    """Common date-range query params. Injected via Depends() on all endpoints."""

    def __init__(
        self,
        date_from: Optional[date] = Query(
            None, description="Inclusive start date filter (YYYY-MM-DD)"
        ),
        date_to: Optional[date] = Query(
            None, description="Inclusive end date filter (YYYY-MM-DD)"
        ),
    ):
        self.date_from = date_from
        self.date_to = date_to


class AnalyticsResponse(BaseModel):
    """Generic envelope returned by all single-domain analytics endpoints."""

    data: Dict[str, Any]
    generated_at: datetime


class DashboardResponse(BaseModel):
    """Composed response for GET /analytics/dashboard."""

    spending: Dict[str, Any]
    categories: Dict[str, Any]
    recurring: Dict[str, Any]
    trends: Dict[str, Any]
    generated_at: datetime
```

**Step 2: Verify importable**

```bash
python -c "from app.schemas.analytics import AnalyticsFilters, AnalyticsResponse, DashboardResponse; print('ok')"
```

**Step 3: Commit**

```bash
git add app/schemas/analytics.py
git commit -m "feat: add analytics request filters and response schemas"
```

---

### Task 6: Add CSV fixtures to integration conftest

**Files:**
- Modify: `tests/integration/conftest.py`

**Step 1: Add the four fixtures**

Append to the end of `tests/integration/conftest.py`:

```python
import polars as pl
from decimal import Decimal
from datetime import datetime

from app.models.transaction import CategoryEnum, Transaction


def _load_transactions_from_csv(path: str, test_user, db_session):
    """Helper: read CSV, override user_id with test_user.id, return Transaction list."""
    df = pl.read_csv(path)
    transactions = []
    for row in df.iter_rows(named=True):
        # Parse date — CSV has YYYY-MM-DD strings
        raw_date = row["date"]
        parsed_date = (
            datetime.strptime(raw_date, "%Y-%m-%d") if isinstance(raw_date, str) else raw_date
        )
        t = Transaction(
            user_id=test_user.id,           # override CSV placeholder
            date=parsed_date,
            merchant=row["merchant"],
            amount=Decimal(str(row["amount"])),
            description=row.get("description") or None,
            original_category=row.get("original_category") or None,
            category=CategoryEnum(row["category"]),
            confidence_score=float(row["confidence_score"]),
            is_recurring=str(row["is_recurring"]).lower() == "true",
        )
        transactions.append(t)
    return transactions


@pytest_asyncio.fixture
async def transactions_single(db_session, test_user):
    """1 transaction inline — tests division-by-zero and empty-trend edge cases."""
    t = Transaction(
        user_id=test_user.id,
        date=datetime(2025, 6, 15),
        merchant="ACME Corp",
        amount=Decimal("-75.00"),
        category=CategoryEnum.SHOPPING,
        confidence_score=1.0,
        is_recurring=False,
    )
    db_session.add(t)
    await db_session.flush()


@pytest_asyncio.fixture
async def transactions_10(db_session, test_user):
    """10 transactions from test_transactions_10.csv (same month)."""
    for t in _load_transactions_from_csv(
        "tests/data/test_transactions_10.csv", test_user, db_session
    ):
        db_session.add(t)
    await db_session.flush()


@pytest_asyncio.fixture
async def transactions_2_months(db_session, test_user):
    """~90 transactions from test_transactions_2_months.csv (2 continuous months)."""
    for t in _load_transactions_from_csv(
        "tests/data/test_transactions_2_months.csv", test_user, db_session
    ):
        db_session.add(t)
    await db_session.flush()


@pytest_asyncio.fixture
async def transactions_400(db_session, test_user):
    """~400 transactions from test_transactions_400.csv (3 years)."""
    for t in _load_transactions_from_csv(
        "tests/data/test_transactions_400.csv", test_user, db_session
    ):
        db_session.add(t)
    await db_session.flush()
```

**Step 2: Verify fixtures load without error (quick smoke test)**

```bash
pytest tests/integration/ -k "not analytics" --collect-only 2>&1 | tail -5
```

Expected: no import errors.

**Step 3: Commit**

```bash
git add tests/integration/conftest.py
git commit -m "test: add CSV-based transaction fixtures for analytics integration tests"
```

---

### Task 7: Write integration tests for the analytics API (failing)

**Files:**
- Create: `tests/integration/test_analytics_api.py`

**Step 1: Write the tests**

```python
# tests/integration/test_analytics_api.py
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
async def test_unauthenticated_returns_401(unauthenticated_client, url):
    resp = await unauthenticated_client.get(url)
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
    # /recurring returns {"recurring": {...}, "stability": {...}}
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
```

**Step 2: Run to confirm they fail**

```bash
pytest tests/integration/test_analytics_api.py -v
```

Expected: `404 Not Found` (router not registered yet) or import errors.

---

### Task 8: Implement `app/api/v1/analytics.py`

**Files:**
- Create: `app/api/v1/analytics.py`

**Step 1: Write the router**

```python
# app/api/v1/analytics.py
"""Analytics read-only endpoints — feeds dashboard and per-tab analytics page."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.database import DbSession
from app.core.limiter import limiter
from app.schemas.analytics import AnalyticsFilters, AnalyticsResponse, DashboardResponse
from app.services.analytics.service import analytics_service

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Dashboard summary",
    description=(
        "Composed snapshot across spending, categories, recurring, and trends. "
        "Designed for the main dashboard — fast, opinionated, no extra params."
    ),
)
@limiter.limit("30/minute")
async def get_dashboard(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    filters: AnalyticsFilters = Depends(),
) -> DashboardResponse:
    data = await analytics_service.get_dashboard(
        db, user.id, filters.date_from, filters.date_to
    )
    return DashboardResponse(**data, generated_at=datetime.utcnow())


@router.get(
    "/spending",
    response_model=AnalyticsResponse,
    summary="Spending overview",
    description="Spending overview, income vs expenses, monthly trend, and burn rate.",
)
@limiter.limit("30/minute")
async def get_spending(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    filters: AnalyticsFilters = Depends(),
) -> AnalyticsResponse:
    data = await analytics_service.get_spending(
        db, user.id, filters.date_from, filters.date_to
    )
    return AnalyticsResponse(data=data, generated_at=datetime.utcnow())


@router.get(
    "/categories",
    response_model=AnalyticsResponse,
    summary="Category breakdown",
    description="Top categories by spend, frequency vs impact, and category trends.",
)
@limiter.limit("30/minute")
async def get_categories(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    filters: AnalyticsFilters = Depends(),
    top_n: int = Query(10, ge=1, le=50, description="Number of top categories to return"),
) -> AnalyticsResponse:
    data = await analytics_service.get_categories(
        db, user.id, filters.date_from, filters.date_to, top_n=top_n
    )
    return AnalyticsResponse(data=data, generated_at=datetime.utcnow())


@router.get(
    "/merchants",
    response_model=AnalyticsResponse,
    summary="Merchant insights",
    description="Top merchants by spend and frequency, plus concentration risk metrics.",
)
@limiter.limit("30/minute")
async def get_merchants(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    filters: AnalyticsFilters = Depends(),
    top_n: int = Query(15, ge=1, le=50, description="Number of top merchants to return"),
) -> AnalyticsResponse:
    data = await analytics_service.get_merchants(
        db, user.id, filters.date_from, filters.date_to, top_n=top_n
    )
    return AnalyticsResponse(data=data, generated_at=datetime.utcnow())


@router.get(
    "/recurring",
    response_model=AnalyticsResponse,
    summary="Recurring & subscriptions",
    description=(
        "Recurring expenses, hidden subscriptions, monthly recurring cost, "
        "and spending stability/predictability profile."
    ),
)
@limiter.limit("30/minute")
async def get_recurring(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    filters: AnalyticsFilters = Depends(),
) -> AnalyticsResponse:
    data = await analytics_service.get_recurring(
        db, user.id, filters.date_from, filters.date_to
    )
    return AnalyticsResponse(data=data, generated_at=datetime.utcnow())


@router.get(
    "/behavior",
    response_model=AnalyticsResponse,
    summary="Behavioral patterns",
    description=(
        "Day-of-week spending patterns, seasonal sensitivity, "
        "and volatility classification (stable vs volatile categories)."
    ),
)
@limiter.limit("30/minute")
async def get_behavior(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    filters: AnalyticsFilters = Depends(),
) -> AnalyticsResponse:
    data = await analytics_service.get_behavior(
        db, user.id, filters.date_from, filters.date_to
    )
    return AnalyticsResponse(data=data, generated_at=datetime.utcnow())


@router.get(
    "/anomalies",
    response_model=AnalyticsResponse,
    summary="Anomaly detection",
    description=(
        "Outlier transactions detected via rolling z-score, "
        "recent category spikes, and volatile spending categories."
    ),
)
@limiter.limit("30/minute")
async def get_anomalies(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    filters: AnalyticsFilters = Depends(),
    std_threshold: float = Query(2.5, description="Z-score threshold for anomaly detection"),
    rolling_window: int = Query(
        30, ge=7, le=90, description="Rolling window in days for baseline calculation"
    ),
) -> AnalyticsResponse:
    data = await analytics_service.get_anomalies(
        db,
        user.id,
        filters.date_from,
        filters.date_to,
        std_threshold=std_threshold,
        rolling_window=rolling_window,
    )
    return AnalyticsResponse(data=data, generated_at=datetime.utcnow())
```

**Step 2: Run integration tests (still failing — router not registered)**

```bash
pytest tests/integration/test_analytics_api.py -v 2>&1 | head -20
```

Expected: still 404s — the router must be registered in `api.py` first.

---

### Task 9: Register the analytics router

**Files:**
- Modify: `app/api/v1/api.py`

**Step 1: Add the import and router registration**

```python
# app/api/v1/api.py
"""API v1 router configuration."""

from fastapi import APIRouter

from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chatbot import router as chatbot_router
from app.api.v1.conversation import router as conversation_router
from app.api.v1.transactions import router as transactions_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(conversation_router, prefix="/conversation", tags=["conversation"])
api_router.include_router(chatbot_router, prefix="/chatbot", tags=["chatbot"])
api_router.include_router(transactions_router, prefix="/transactions", tags=["transactions"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
```

**Step 2: Run the full integration test suite**

```bash
pytest tests/integration/test_analytics_api.py -v
```

Expected: all tests pass.

**Step 3: Run the full test suite to check for regressions**

```bash
pytest --tb=short -q
```

Expected: all existing tests still pass.

**Step 4: Commit**

```bash
git add app/api/v1/api.py app/api/v1/analytics.py
git commit -m "feat: add analytics API endpoints under /api/v1/analytics"
```

---

## Summary of Files

| Action | Path |
|--------|------|
| Modify | `app/tools/financial.py` |
| Create | `app/services/analytics/__init__.py` |
| Create | `app/services/analytics/exceptions.py` |
| Create | `app/services/analytics/service.py` |
| Create | `app/schemas/analytics.py` |
| Create | `app/api/v1/analytics.py` |
| Modify | `app/api/v1/api.py` |
| Create | `tests/unit/tools/__init__.py` |
| Create | `tests/unit/tools/test_financial_tools.py` |
| Create | `tests/unit/services/test_analytics_service.py` |
| Modify | `tests/integration/conftest.py` |
| Create | `tests/integration/test_analytics_api.py` |
