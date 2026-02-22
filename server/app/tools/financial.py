"""
Analytical Service - Semantic Layer for Finance Coach Agent

This service provides high-level, intent-based tools that wrap the existing
analytics functions. It bridges the gap between user intents (explain, compare,
reflect, diagnose, improve) and low-level analytics (compute, aggregate, detect).

Tools are designed to:
- Accept Polars DataFrames
- Be deterministic (no LLM reasoning)
- Return structured outputs
- Work with LangChain/LangGraph agents
- Be callable as standalone async functions
"""

import polars as pl
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

# Import existing analytics functions
from analytics.descriptive import (
    calculate_spending_overview,
    analyze_by_category,
    analyze_recurring,
    analyze_merchants,
    PeriodEnum
)
from analytics.temporal import (
    calculate_monthly_spending_trend,
    calculate_category_trend,
    analyze_day_of_week_patterns,
    analyze_seasonality_simple,
    analyze_spending_volatility,
    calculate_rolling_averages,
    identify_stable_vs_volatile_categories
)


# ============================================================================
# Input/Output Models
# ============================================================================

class BaseAnalysisInput(BaseModel):
    """Base input for all analysis tools."""
    transactions_df: Dict[str, Any] = Field(description="Transaction data as dict from df.to_dict()")
    start_date: Optional[str] = Field(default=None, description="Start date filter (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, description="End date filter (YYYY-MM-DD)")


class BaseAnalysisOutput(BaseModel):
    """Base output for all analysis tools."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# Validation & Conversion Helpers
# ============================================================================

def _validate_and_convert_df(df_dict: Dict[str, Any]) -> tuple[bool, Optional[str], Optional[pl.DataFrame]]:
    """
    Validate and convert dict to Polars DataFrame.
    
    Returns:
        (success, error_message, dataframe)
    """
    try:
        df = pl.DataFrame(df_dict)
    except Exception as e:
        return False, f"Failed to convert to DataFrame: {str(e)}", None
    
    required_cols = {"date", "merchant", "amount", "category"}
    missing = required_cols - set(df.columns)
    
    if missing:
        return False, f"Missing required columns: {missing}", None
    
    # Replace string 'null' with actual nulls
    for col in df.columns:
        if df[col].dtype == pl.Utf8:
            df = df.with_columns(
                pl.when(pl.col(col) == "null")
                .then(None)
                .otherwise(pl.col(col))
                .alias(col)
            )
    
    # Ensure date is proper type
    if df["date"].dtype == pl.Utf8:
        try:
            df = df.with_columns(pl.col("date").str.to_date())
        except Exception as e:
            return False, f"Invalid date format: {str(e)}", None
    
    # Filter out rows with null dates (essential for temporal analysis)
    original_len = len(df)
    df = df.filter(pl.col("date").is_not_null())
    if len(df) < original_len:
        print(f"⚠️  Filtered out {original_len - len(df)} transactions with null dates")
    
    return True, None, df


def _apply_date_filter(df: pl.DataFrame, start_date: Optional[str], end_date: Optional[str]) -> pl.DataFrame:
    """Apply date range filters if provided."""
    if start_date:
        df = df.filter(pl.col("date") >= pl.lit(start_date).str.to_date())
    if end_date:
        df = df.filter(pl.col("date") <= pl.lit(end_date).str.to_date())
    return df


# ============================================================================
# Semantic Tools - Intent-Based Analytics
# ============================================================================

async def get_spending_summary(
    transactions_df: Dict[str, Any],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Answer: "What is my financial situation?"
    
    Provides a comprehensive spending overview including total spend, income vs expenses,
    net position, average transaction size, and recent period comparison.
    
    Useful for: Understanding overall financial health and recent trends.
    
    Args:
        transactions_df: Transaction data as dict from df.to_dict()
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)
    
    Returns:
        Dictionary with success status, spending summary data, or error
    """
    success, error, df = _validate_and_convert_df(transactions_df)
    if not success:
        return BaseAnalysisOutput(success=False, error=error).model_dump()
    
    try:
        # Apply date filters
        df = _apply_date_filter(df, start_date, end_date)
        
        # Get spending overview
        overview = calculate_spending_overview(df, period=PeriodEnum.MONTHLY)
        
        # Get monthly trends for comparison
        trends = calculate_monthly_spending_trend(df, include_income=True)
        
        # Extract key insights
        summary_stats = overview["summary"].to_dicts()
        income_vs_expenses = overview["income_vs_expenses"].to_dicts()
        recent_months = trends["monthly_trend"].tail(3).to_dicts()
        burn_rate = trends["burn_rate"].to_dicts()
        
        result = {
            "overview": {
                "stats": summary_stats,
                "income_vs_expenses": income_vs_expenses
            },
            "recent_trend": {
                "last_3_months": recent_months,
                "burn_rate": burn_rate
            },
            "date_range": {
                "start": str(df["date"].min()),
                "end": str(df["date"].max()),
                "total_days": int((df["date"].max() - df["date"].min()).days)
            }
        }
        
        return BaseAnalysisOutput(
            success=True,
            data=result,
            metadata={"tool": "get_spending_summary", "intent": "explain_financial_situation"}
        ).model_dump()
    
    except Exception as e:
        return BaseAnalysisOutput(success=False, error=f"Analysis failed: {str(e)}").model_dump()


async def get_category_insights(
    transactions_df: Dict[str, Any],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    top_n: int = 10
) -> Dict[str, Any]:
    """
    Answer: "Where does my money go?"
    
    Provides category-level spending insights including top categories, growth/decline,
    frequency vs impact analysis, and confidence-weighted values.
    
    Useful for: Understanding spending allocation and identifying major expense drivers.
    
    Args:
        transactions_df: Transaction data as dict from df.to_dict()
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)
        top_n: Number of top categories to return (default: 10)
    
    Returns:
        Dictionary with success status, category insights data, or error
    """
    success, error, df = _validate_and_convert_df(transactions_df)
    if not success:
        return BaseAnalysisOutput(success=False, error=error).model_dump()
    
    try:
        df = _apply_date_filter(df, start_date, end_date)
        
        # Get category analysis
        category_data = analyze_by_category(df)
        
        # Get category trends for top categories
        top_categories = category_data["by_category"].head(top_n)["category"].to_list()
        category_trends = {}
        
        for cat in top_categories[:5]:  # Trend for top 5 only
            try:
                trend = calculate_category_trend(df, category=cat)
                category_trends[cat] = trend["category_trend"].tail(6).to_dicts()
            except:
                category_trends[cat] = []
        
        result = {
            "top_categories": category_data["by_category"].head(top_n).to_dicts(),
            "frequency_vs_impact": category_data["frequency_vs_impact"].head(top_n).to_dicts(),
            "confidence_weighted": category_data["confidence_weighted"].head(top_n).to_dicts(),
            "category_trends": category_trends
        }
        
        return BaseAnalysisOutput(
            success=True,
            data=result,
            metadata={"tool": "get_category_insights", "intent": "explain_spending_allocation"}
        ).model_dump()
    
    except Exception as e:
        return BaseAnalysisOutput(success=False, error=f"Analysis failed: {str(e)}").model_dump()


async def get_recurring_insights(
    transactions_df: Dict[str, Any],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Answer: "What am I locked into?"
    
    Identifies recurring expenses, subscription costs, and hidden subscriptions.
    Calculates total recurring load, percentage of expenses, and subscription creep.
    
    Useful for: Understanding fixed costs and identifying potential savings opportunities.
    
    Args:
        transactions_df: Transaction data as dict from df.to_dict()
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)
    
    Returns:
        Dictionary with success status, recurring expense insights, or error
    """
    success, error, df = _validate_and_convert_df(transactions_df)
    if not success:
        return BaseAnalysisOutput(success=False, error=error).model_dump()
    
    try:
        df = _apply_date_filter(df, start_date, end_date)
        
        # Get recurring analysis
        recurring_data = analyze_recurring(df)
        
        # Calculate recurring load and percentage
        summary = recurring_data["recurring_summary"].to_dicts()
        monthly_costs = recurring_data["monthly_recurring_cost"].sort("estimated_monthly_cost", descending=True).to_dicts()
        by_category = recurring_data["recurring_by_category"].to_dicts()
        hidden_subs = recurring_data["hidden_subscriptions"].to_dicts()
        
        # Calculate total recurring as % of expenses
        recurring_summary = next((s for s in summary if s.get("is_recurring") == True), None)
        total_recurring_pct = recurring_summary.get("amount_percentage", 0.0) if recurring_summary else 0.0
        
        result = {
            "recurring_summary": summary,
            "monthly_recurring_costs": monthly_costs,
            "recurring_by_category": by_category,
            "hidden_subscriptions": hidden_subs,
            "insights": {
                "total_recurring_percentage": total_recurring_pct,
                "total_hidden_subscriptions": len(hidden_subs),
                "top_recurring_merchant": monthly_costs[0]["merchant"] if monthly_costs else None
            }
        }
        
        return BaseAnalysisOutput(
            success=True,
            data=result,
            metadata={"tool": "get_recurring_insights", "intent": "diagnose_fixed_costs"}
        ).model_dump()
    
    except Exception as e:
        return BaseAnalysisOutput(success=False, error=f"Analysis failed: {str(e)}").model_dump()


async def get_trend_insights(
    transactions_df: Dict[str, Any],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Answer: "What changed recently?"
    
    Analyzes spending trends including MoM/YoY growth, burn rate, fastest growing
    categories, and slowdown signals.
    
    Useful for: Identifying spending pattern changes and emerging trends.
    
    Args:
        transactions_df: Transaction data as dict from df.to_dict()
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)
    
    Returns:
        Dictionary with success status, trend insights, or error
    """
    success, error, df = _validate_and_convert_df(transactions_df)
    if not success:
        return BaseAnalysisOutput(success=False, error=error).model_dump()
    
    try:
        df = _apply_date_filter(df, start_date, end_date)
        
        # Get monthly trends
        monthly_data = calculate_monthly_spending_trend(df, include_income=True)
        
        # Get category analysis to find fastest growing
        category_data = analyze_by_category(df)
        top_categories = category_data["by_category"].head(10)["category"].to_list()
        
        # Calculate growth rates for top categories
        category_growth = []
        for cat in top_categories[:8]:
            try:
                trend = calculate_category_trend(df, category=cat)
                recent_months = trend["category_trend"].tail(6)
                if len(recent_months) >= 2:
                    latest = recent_months["monthly_spending"].to_list()[-1]
                    previous = recent_months["monthly_spending"].to_list()[0]
                    growth_rate = ((latest - previous) / previous * 100) if previous > 0 else 0
                    
                    category_growth.append({
                        "category": cat,
                        "growth_rate": growth_rate,
                        "latest_month_spending": latest,
                        "trend_data": recent_months.to_dicts()
                    })
            except:
                continue
        
        # Sort by growth rate
        category_growth.sort(key=lambda x: x["growth_rate"], reverse=True)
        
        result = {
            "monthly_trend": monthly_data["monthly_trend"].tail(12).to_dicts(),
            "year_comparison": monthly_data["year_comparison"].to_dicts() if len(monthly_data["year_comparison"]) > 0 else [],
            "burn_rate": monthly_data["burn_rate"].to_dicts(),
            "fastest_growing_categories": category_growth[:5],
            "declining_categories": category_growth[-3:],
            "insights": {
                "latest_mom_growth": monthly_data["monthly_trend"]["expense_mom_growth"].tail(1).to_list()[0] if len(monthly_data["monthly_trend"]) > 0 else None,
                "categories_analyzed": len(category_growth)
            }
        }
        
        return BaseAnalysisOutput(
            success=True,
            data=result,
            metadata={"tool": "get_trend_insights", "intent": "compare_periods"}
        ).model_dump()
    
    except Exception as e:
        return BaseAnalysisOutput(success=False, error=f"Analysis failed: {str(e)}").model_dump()


async def get_behavioral_patterns(
    transactions_df: Dict[str, Any],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Answer: "How do I behave financially?"
    
    Analyzes behavioral spending patterns including weekend bias, day-of-week patterns,
    seasonal sensitivity, and spending volatility (stable vs volatile categories).
    
    Useful for: Understanding spending habits and identifying behavioral triggers.
    
    Args:
        transactions_df: Transaction data as dict from df.to_dict()
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)
    
    Returns:
        Dictionary with success status, behavioral pattern insights, or error
    """
    success, error, df = _validate_and_convert_df(transactions_df)
    if not success:
        return BaseAnalysisOutput(success=False, error=error).model_dump()
    
    try:
        df = _apply_date_filter(df, start_date, end_date)
        
        # Day of week patterns
        dow_data = analyze_day_of_week_patterns(df)
        
        # Seasonality analysis
        seasonality_data = analyze_seasonality_simple(df)
        
        # Volatility analysis
        volatility_data = analyze_spending_volatility(df)
        
        # Calculate behavioral insights
        weekday_vs_weekend = dow_data["weekday_vs_weekend"].to_dicts()
        weekend_bias = None
        if len(weekday_vs_weekend) == 2:
            weekend_row = next((r for r in weekday_vs_weekend if r["day_type"] == "weekend"), None)
            weekday_row = next((r for r in weekday_vs_weekend if r["day_type"] == "weekday"), None)
            if weekend_row and weekday_row:
                weekend_bias = (weekend_row["avg_per_day"] / weekday_row["avg_per_day"] - 1) * 100
        
        result = {
            "day_of_week": {
                "by_weekday": dow_data["by_weekday"].to_dicts(),
                "weekday_vs_weekend": weekday_vs_weekend,
                "weekend_bias_percentage": weekend_bias
            },
            "seasonality": {
                "monthly_patterns": seasonality_data["monthly_seasonality"].to_dicts(),
                "monthly_volatility": seasonality_data["month_volatility"].to_dicts() if "month_volatility" in seasonality_data else [],
                "quarterly_patterns": seasonality_data["quarterly_seasonality"].to_dicts() if "quarterly_seasonality" in seasonality_data else []
            },
            "volatility": {
                "stable_categories": volatility_data["stable_categories"].head(5).to_dicts(),
                "volatile_categories": volatility_data["volatile_categories"].head(5).to_dicts(),
                "category_volatility": volatility_data["category_volatility"].to_dicts()
            },
            "insights": {
                "weekend_spender": weekend_bias > 10 if weekend_bias else False,
                "most_stable_category": volatility_data["stable_categories"]["category"].head(1).to_list()[0] if len(volatility_data["stable_categories"]) > 0 else None,
                "most_volatile_category": volatility_data["volatile_categories"]["category"].head(1).to_list()[0] if len(volatility_data["volatile_categories"]) > 0 else None
            }
        }
        
        return BaseAnalysisOutput(
            success=True,
            data=result,
            metadata={"tool": "get_behavioral_patterns", "intent": "reflect_on_habits"}
        ).model_dump()
    
    except Exception as e:
        return BaseAnalysisOutput(success=False, error=f"Analysis failed: {str(e)}").model_dump()


async def get_anomaly_insights(
    transactions_df: Dict[str, Any],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    std_threshold: float = 2.5,
    rolling_window: int = 30
) -> Dict[str, Any]:
    """
    Answer: "What looks unusual?"
    
    Detects anomalous spending patterns including outlier transactions, abnormal weeks,
    and category spikes based on rolling averages and volatility analysis.
    
    Useful for: Identifying unusual spending, potential fraud, or one-time expenses.
    
    Args:
        transactions_df: Transaction data as dict from df.to_dict()
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)
        std_threshold: Standard deviation threshold for anomalies (default: 2.5)
        rolling_window: Rolling window in days (default: 30)
    
    Returns:
        Dictionary with success status, anomaly insights, or error
    """
    success, error, df = _validate_and_convert_df(transactions_df)
    if not success:
        return BaseAnalysisOutput(success=False, error=error).model_dump()
    
    try:
        df = _apply_date_filter(df, start_date, end_date)
        
        # Sort by date
        df = df.sort("date")
        
        # Calculate rolling averages (pass rolling_window as a list)
        rolling_stats = calculate_rolling_averages(df, windows=[rolling_window])
        
        # Get volatility data
        volatility_data = analyze_spending_volatility(df)
        
        # Join rolling stats with transactions for anomaly detection
        df_with_stats = df.join(
            rolling_stats.select(["date", f"rolling_avg_{rolling_window}d", f"rolling_std_{rolling_window}d"]),
            on="date",
            how="left"
        )
        
        # Detect anomalies (expenses only, absolute values)
        df_expenses = df_with_stats.filter(pl.col("amount") < 0).with_columns([
            pl.col("amount").abs().alias("amount_abs")
        ])
        
        df_anomalies = df_expenses.with_columns([
            ((pl.col("amount_abs") - pl.col(f"rolling_avg_{rolling_window}d")) / 
             pl.col(f"rolling_std_{rolling_window}d")).abs().alias("z_score")
        ]).filter(
            pl.col("z_score") > std_threshold
        ).sort("z_score", descending=True)
        
        # Category spikes: compare recent month to average
        df_recent = df.filter(pl.col("date") >= df["date"].max() - pl.duration(days=30))
        recent_by_cat = df_recent.filter(pl.col("amount") < 0).group_by("category").agg([
            pl.col("amount").abs().sum().alias("recent_spending")
        ])
        
        overall_by_cat = df.filter(pl.col("amount") < 0).group_by("category").agg([
            pl.col("amount").abs().mean().alias("avg_monthly_spending")
        ])
        
        category_spikes = recent_by_cat.join(overall_by_cat, on="category").with_columns([
            (((pl.col("recent_spending") / pl.col("avg_monthly_spending")) - 1) * 100).alias("spike_percentage")
        ]).filter(
            pl.col("spike_percentage") > 50
        ).sort("spike_percentage", descending=True)
        
        result = {
            "outlier_transactions": df_anomalies.select([
                "date", "merchant", "amount_abs", "category", "z_score", f"rolling_avg_{rolling_window}d"
            ]).head(20).to_dicts(),
            "category_spikes": category_spikes.to_dicts(),
            "volatility_summary": volatility_data["volatile_categories"].head(5).to_dicts(),
            "insights": {
                "total_anomalies": len(df_anomalies),
                "highest_z_score": float(df_anomalies["z_score"].max()) if len(df_anomalies) > 0 else 0,
                "categories_spiking": len(category_spikes),
                "detection_window_days": rolling_window,
                "threshold_std": std_threshold
            }
        }
        
        return BaseAnalysisOutput(
            success=True,
            data=result,
            metadata={"tool": "get_anomaly_insights", "intent": "diagnose_unusual_spending"}
        ).model_dump()
    
    except Exception as e:
        return BaseAnalysisOutput(success=False, error=f"Analysis failed: {str(e)}").model_dump()


async def get_merchant_insights(
    transactions_df: Dict[str, Any],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    top_n: int = 15
) -> Dict[str, Any]:
    """
    Answer: "Which merchants control my spending?"
    
    Analyzes merchant-level spending patterns including concentration risk,
    frequency analysis, and one-off vs recurring merchant classification.
    
    Useful for: Understanding vendor lock-in and identifying spending concentration.
    
    Args:
        transactions_df: Transaction data as dict from df.to_dict()
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)
        top_n: Number of top merchants to analyze (default: 15)
    
    Returns:
        Dictionary with success status, merchant insights data, or error
    """
    success, error, df = _validate_and_convert_df(transactions_df)
    if not success:
        return BaseAnalysisOutput(success=False, error=error).model_dump()
    
    try:
        df = _apply_date_filter(df, start_date, end_date)
        
        # Get merchant analysis
        merchant_data = analyze_merchants(df, top_n=top_n)
        
        # Calculate concentration metrics (Herfindahl-style)
        top_merchants = merchant_data["top_merchants"]
        total_spending = top_merchants["total_amount"].sum()
        
        top_5_pct = (top_merchants.head(5)["total_amount"].sum() / total_spending * 100) if total_spending > 0 else 0
        top_10_pct = (top_merchants.head(10)["total_amount"].sum() / total_spending * 100) if total_spending > 0 else 0
        
        # Calculate Herfindahl index (concentration metric: 0-10000, higher = more concentrated)
        merchant_summary = merchant_data["merchant_summary"]
        if len(merchant_summary) > 0:
            total_merchants = len(merchant_summary)
            market_shares = (merchant_summary["total_amount"] / total_spending * 100).to_list() if total_spending > 0 else []
            herfindahl = sum([share ** 2 for share in market_shares])
        else:
            herfindahl = 0
            total_merchants = 0
        
        one_off_vs_frequent = merchant_data["one_off_vs_frequent"].to_dicts()
        
        result = {
            "top_merchants": top_merchants.head(top_n).to_dicts(),
            "by_frequency": merchant_data["by_frequency"].head(top_n).to_dicts(),
            "merchant_classification": one_off_vs_frequent,
            "concentration_metrics": {
                "top_5_merchants_pct": top_5_pct,
                "top_10_merchants_pct": top_10_pct,
                "herfindahl_index": herfindahl,
                "total_unique_merchants": total_merchants,
                "concentration_risk": "high" if herfindahl > 2500 else "medium" if herfindahl > 1500 else "low"
            }
        }
        
        return BaseAnalysisOutput(
            success=True,
            data=result,
            metadata={"tool": "get_merchant_insights", "intent": "diagnose_merchant_concentration"}
        ).model_dump()
    
    except Exception as e:
        return BaseAnalysisOutput(success=False, error=f"Analysis failed: {str(e)}").model_dump()


async def get_spending_stability_profile(
    transactions_df: Dict[str, Any],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Answer: "How predictable is my spending?"
    
    Comprehensive spending predictability analysis including stability classification,
    spending baseline, discretionary ceiling, and subscription creep detection.
    
    Useful for: Budgeting, understanding fixed vs variable costs, and forecasting.
    
    Args:
        transactions_df: Transaction data as dict from df.to_dict()
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)
    
    Returns:
        Dictionary with success status, stability profile data, or error
    """
    success, error, df = _validate_and_convert_df(transactions_df)
    if not success:
        return BaseAnalysisOutput(success=False, error=error).model_dump()
    
    try:
        df = _apply_date_filter(df, start_date, end_date)
        
        # Get stability classification
        stability_data = identify_stable_vs_volatile_categories(df)
        
        # Get volatility details
        volatility_data = analyze_spending_volatility(df)
        
        # Get recurring data for subscription creep
        recurring_data = analyze_recurring(df)
        monthly_trends = calculate_monthly_spending_trend(df, include_income=True)
        
        # Calculate stability profile percentages
        classification_summary = stability_data["classification_summary"].to_dicts()
        total_spending = sum([row.get("total_spending", 0) for row in classification_summary])
        
        stable_pct = 0
        moderate_pct = 0
        volatile_pct = 0
        
        for row in classification_summary:
            pct = (row.get("total_spending", 0) / total_spending * 100) if total_spending > 0 else 0
            if row["stability_class"] == "stable":
                stable_pct = pct
            elif row["stability_class"] == "moderate":
                moderate_pct = pct
            elif row["stability_class"] == "volatile":
                volatile_pct = pct
        
        # Calculate subscription creep (MoM change in recurring)
        subscription_creep = None
        recurring_summary = recurring_data["recurring_summary"].to_dicts()
        if len(monthly_trends["monthly_trend"]) >= 2:
            recent_months = monthly_trends["monthly_trend"].tail(2)
            if len(recent_months) == 2:
                months_data = recent_months.to_dicts()
                if len(months_data) >= 2:
                    latest_expense = months_data[-1].get("total_expenses", 0)
                    previous_expense = months_data[-2].get("total_expenses", 0)
                    if previous_expense > 0:
                        subscription_creep = ((latest_expense - previous_expense) / previous_expense * 100)
        
        result = {
            "stability_distribution": {
                "stable_percentage": stable_pct,
                "moderate_percentage": moderate_pct,
                "volatile_percentage": volatile_pct
            },
            "stable_categories": stability_data["stable"].head(10).to_dicts(),
            "moderate_categories": stability_data["moderate"].head(10).to_dicts(),
            "volatile_categories": stability_data["volatile"].head(10).to_dicts(),
            "volatility_metrics": volatility_data["category_volatility"].head(15).to_dicts(),
            "recurring_insights": recurring_summary,
            "subscription_creep": {
                "mom_change_percentage": subscription_creep,
                "status": "creeping_up" if subscription_creep and subscription_creep > 5 else 
                         "creeping_down" if subscription_creep and subscription_creep < -5 else 
                         "stable"
            },
            "insights": {
                "predictable_baseline_pct": stable_pct,
                "discretionary_portion_pct": volatile_pct,
                "stability_profile": "high_predictability" if stable_pct > 60 else 
                                    "moderate_predictability" if stable_pct > 40 else 
                                    "low_predictability"
            }
        }
        
        return BaseAnalysisOutput(
            success=True,
            data=result,
            metadata={"tool": "get_spending_stability_profile", "intent": "reflect_on_predictability"}
        ).model_dump()
    
    except Exception as e:
        return BaseAnalysisOutput(success=False, error=f"Analysis failed: {str(e)}").model_dump()


# ============================================================================
# Tool Registry
# ============================================================================

ANALYTICAL_TOOLS = [
    get_spending_summary,
    get_category_insights,
    get_recurring_insights,
    get_trend_insights,
    get_behavioral_patterns,
    get_anomaly_insights,
    get_merchant_insights,
    get_spending_stability_profile
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
    "get_spending_stability_profile"
]
