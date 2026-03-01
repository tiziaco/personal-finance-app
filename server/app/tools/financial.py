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


_EMPTY_RESPONSE: Dict[str, Any] = {}


def _empty_df_response(keys: list) -> Dict[str, Any]:
    return {k: [] for k in keys}


async def get_spending_summary(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Answer: "What is my financial situation?"

    Provides a comprehensive spending overview including total spend,
    income vs expenses, net position, and recent period comparison.
    """
    if len(df) == 0:
        return {
            "overview": {"stats": [], "income_vs_expenses": []},
            "recent_trend": {"last_3_months": [], "burn_rate": []},
            "date_range": {"start": None, "end": None, "total_days": 0},
        }
    overview = calculate_spending_overview(
        df, period=PeriodEnum.MONTHLY, start_date=start_date, end_date=end_date
    )
    trends = calculate_monthly_spending_trend(
        df, start_date=start_date, end_date=end_date, include_income=True
    )

    monthly_stats = [
        {
            "month": f"{row['year']:04d}-{row['month']:02d}",
            "total_income": row["total_income"],
            "total_expense": row["total_expenses"],
            "net": row["net_amount"],
            "expense_mom_growth": (
                row["expense_mom_growth"] * 100
                if row["expense_mom_growth"] is not None
                else None
            ),
        }
        for row in trends["monthly_trend"].to_dicts()
    ]

    return {
        "overview": {
            "stats": monthly_stats,
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
    if len(df) == 0:
        return {
            "recurring_summary": [],
            "monthly_recurring_costs": [],
            "recurring_by_category": [],
            "hidden_subscriptions": [],
            "insights": {
                "total_recurring_percentage": 0.0,
                "total_hidden_subscriptions": 0,
                "top_recurring_merchant": None,
            },
        }
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
    if len(df) == 0:
        return {
            "monthly_trend": [],
            "year_comparison": [],
            "burn_rate": [],
            "top_growing": [],
            "top_declining": [],
            "insights": {"latest_mom_growth": None},
        }
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
    if len(df) == 0:
        return {
            "outlier_transactions": [],
            "category_spikes": [],
            "volatility_summary": [],
            "insights": {
                "total_anomalies": 0,
                "highest_z_score": 0.0,
                "categories_spiking": 0,
                "detection_window_days": rolling_window,
                "threshold_std": std_threshold,
            },
        }
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
    if len(df) == 0:
        return {
            "stability_distribution": {
                "stable_percentage": 0.0,
                "moderate_percentage": 0.0,
                "volatile_percentage": 0.0,
            },
            "stable_categories": [],
            "moderate_categories": [],
            "volatile_categories": [],
            "volatility_metrics": [],
            "recurring_insights": [],
            "subscription_creep": {"mom_change_percentage": None, "status": "stable"},
            "insights": {
                "predictable_baseline_pct": 0.0,
                "discretionary_portion_pct": 0.0,
                "stability_profile": "low_predictability",
            },
        }
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
