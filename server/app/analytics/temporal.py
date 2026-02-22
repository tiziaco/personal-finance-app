"""
Temporal & Trend Analytics Module for Personal Finance App

This module provides comprehensive time-series and trend analytics for transaction data.
All methods operate on DataFrames with columns: date, merchant, amount, category, confidence_score, is_recurring

Analytics Categories:
- Time-Series Aggregations: Monthly trends, category trends, rolling averages
- Seasonality & Cycles: Seasonal patterns, day-of-week analysis, payday proximity
- Volatility & Stability: Variance analysis, stable vs volatile categories

Dependencies:
- Core: polars (required)
- Optional: statsmodels (for advanced seasonal decomposition)
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import date, datetime
import polars as pl
from statsmodels.tsa.seasonal import seasonal_decompose


class RollingWindowEnum(str, Enum):
    """Rolling window periods for trend analysis"""
    WEEK = "7d"
    MONTH = "30d"
    QUARTER = "90d"


class SeasonalityPeriodEnum(str, Enum):
    """Seasonality detection periods"""
    MONTHLY = "monthly"  # 12-month cycle
    QUARTERLY = "quarterly"  # 4-quarter cycle
    WEEKLY = "weekly"  # 52-week cycle


# ============================================================================
# HELPER FUNCTIONS (INTERNAL)
# ============================================================================

def _prepare_dataframe(df: pl.DataFrame) -> pl.DataFrame:
    """
    Prepare transaction DataFrame for analytics by ensuring correct data types.
    
    Args:
        df: Raw transaction DataFrame
        
    Returns:
        Prepared DataFrame with proper types
    """
    prepared = df.clone()
    
    # Ensure date column is proper date type
    if prepared["date"].dtype != pl.Date:
        prepared = prepared.with_columns([
            pl.col("date").str.to_date().alias("date")
        ])
    
    # Ensure numeric types
    prepared = prepared.with_columns([
        pl.col("amount").cast(pl.Float64),
        pl.col("confidence_score").cast(pl.Float64),
    ])
    
    # Ensure boolean type for is_recurring
    if prepared["is_recurring"].dtype != pl.Boolean:
        prepared = prepared.with_columns([
            pl.col("is_recurring").cast(pl.Boolean)
        ])
    
    return prepared


def _filter_by_date_range(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> pl.DataFrame:
    """
    Filter DataFrame by date range.
    
    Args:
        df: Transaction DataFrame
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        
    Returns:
        Filtered DataFrame
    """
    filtered = df.clone()
    
    if start_date:
        filtered = filtered.filter(pl.col("date") >= start_date)
    
    if end_date:
        filtered = filtered.filter(pl.col("date") <= end_date)
    
    return filtered


def _get_expenses_only(df: pl.DataFrame) -> pl.DataFrame:
    """
    Extract and prepare expenses (negative amounts) from DataFrame.
    
    Args:
        df: Transaction DataFrame
        
    Returns:
        DataFrame with expenses only, amounts made positive
    """
    return df.filter(pl.col("amount") < 0).with_columns([
        pl.col("amount").abs().alias("amount")
    ])


def _add_temporal_features(df: pl.DataFrame) -> pl.DataFrame:
    """
    Add temporal feature columns for analysis.
    
    Args:
        df: Transaction DataFrame
        
    Returns:
        DataFrame with additional temporal columns:
        - year, month, week, day, weekday, quarter
        - month_name, day_name for readability
    """
    return df.with_columns([
        pl.col("date").dt.year().alias("year"),
        pl.col("date").dt.month().alias("month"),
        pl.col("date").dt.week().alias("week"),
        pl.col("date").dt.day().alias("day"),
        pl.col("date").dt.weekday().alias("weekday"),
        pl.col("date").dt.quarter().alias("quarter"),
        pl.col("date").dt.strftime("%B").alias("month_name"),
        pl.col("date").dt.strftime("%A").alias("day_name"),
    ])


def _fill_missing_dates(
    df: pl.DataFrame,
    date_col: str = "date",
    value_cols: Optional[List[str]] = None,
    fill_value: float = 0.0
) -> pl.DataFrame:
    """
    Fill missing dates in time series with specified fill value.
    
    Args:
        df: DataFrame with date column
        date_col: Name of the date column
        value_cols: Columns to fill with fill_value (others forward-filled)
        fill_value: Value to use for missing dates
        
    Returns:
        DataFrame with complete date range
    """
    if len(df) == 0:
        return df
    
    # Create complete date range
    min_date = df[date_col].min()
    max_date = df[date_col].max()
    
    date_range = pl.DataFrame({
        date_col: pl.date_range(min_date, max_date, interval="1d", eager=True)
    })
    
    # Join with original data
    filled = date_range.join(df, on=date_col, how="left")
    
    # Fill missing values
    if value_cols:
        for col in value_cols:
            if col in filled.columns:
                filled = filled.with_columns([
                    pl.col(col).fill_null(fill_value)
                ])
    
    return filled


# ============================================================================
# TIME-SERIES AGGREGATIONS
# ============================================================================

def calculate_monthly_spending_trend(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    include_income: bool = False
) -> Dict[str, pl.DataFrame]:
    """
    Calculate monthly spending trends over time.
    
    Provides:
    - Monthly total spending
    - Month-over-month (MoM) growth rate
    - Year-over-year (YoY) comparison when applicable
    - Cumulative spending
    
    Args:
        df: Transaction DataFrame
        start_date: Optional start date filter
        end_date: Optional end date filter
        include_income: Whether to include income in the analysis
        
    Returns:
        Dictionary containing:
        - 'monthly_trend': Monthly spending with growth rates
        - 'year_comparison': Year-over-year comparison by month
        - 'burn_rate': Average monthly burn rate metrics
    """
    # Prepare and filter data
    df = _prepare_dataframe(df)
    df = _filter_by_date_range(df, start_date, end_date)
    df = _add_temporal_features(df)
    
    # Filter for expenses (or include all if include_income=True)
    if not include_income:
        df = _get_expenses_only(df)
    else:
        # Separate income and expenses for analysis
        df = df.with_columns([
            pl.when(pl.col("amount") > 0)
            .then(pl.col("amount"))
            .otherwise(0.0)
            .alias("income"),
            pl.when(pl.col("amount") < 0)
            .then(pl.col("amount").abs())
            .otherwise(0.0)
            .alias("expense")
        ])
    
    # Monthly aggregation
    if include_income:
        monthly_trend = df.group_by(["year", "month", "month_name"]).agg([
            pl.col("income").sum().alias("total_income"),
            pl.col("expense").sum().alias("total_expenses"),
            pl.len().alias("transaction_count"),
        ]).sort(["year", "month"])
        
        # Calculate burn rates
        avg_monthly_income = monthly_trend["total_income"].mean()
        avg_monthly_expenses = monthly_trend["total_expenses"].mean()
        net_burn_rate = avg_monthly_expenses - avg_monthly_income
        
        # Add net and growth calculations
        monthly_trend = monthly_trend.with_columns([
            (pl.col("total_income") - pl.col("total_expenses")).alias("net_amount"),
            pl.col("total_expenses").pct_change().alias("expense_mom_growth"),
            pl.col("total_income").pct_change().alias("income_mom_growth"),
        ])
    else:
        monthly_trend = df.group_by(["year", "month", "month_name"]).agg([
            pl.col("amount").sum().alias("total_spending"),
            pl.col("amount").mean().alias("avg_transaction"),
            pl.len().alias("transaction_count"),
        ]).sort(["year", "month"])
        
        # Calculate burn rate (average monthly spending)
        avg_monthly_expenses = monthly_trend["total_spending"].mean()
        net_burn_rate = avg_monthly_expenses  # Same as gross when no income
        
        # Add month-over-month growth and cumulative spending
        monthly_trend = monthly_trend.with_columns([
            pl.col("total_spending").pct_change().alias("mom_growth_rate"),
            pl.col("total_spending").cum_sum().alias("cumulative_spending"),
        ])
    
    # Year-over-year comparison (only if we have multiple years)
    years = df["year"].unique().sort()
    
    if len(years) > 1:
        year_comparison = df.group_by(["year", "month", "month_name"]).agg([
            pl.col("amount" if not include_income else "expense").sum().alias("total_spending"),
        ]).sort(["month", "year"])
        
        # Pivot to compare years side by side
        year_comparison = year_comparison.pivot(
            values="total_spending",
            index=["month", "month_name"],
            columns="year"
        ).sort("month")
        
        # Calculate YoY growth if we have consecutive years
        year_cols = [col for col in year_comparison.columns if col not in ["month", "month_name"]]
        if len(year_cols) >= 2:
            # Add YoY growth for most recent year
            latest_year = max([int(col) for col in year_cols])
            previous_year = latest_year - 1
            
            if str(previous_year) in year_comparison.columns and str(latest_year) in year_comparison.columns:
                year_comparison = year_comparison.with_columns([
                    ((pl.col(str(latest_year)) - pl.col(str(previous_year))) / 
                     pl.col(str(previous_year)) * 100).alias(f"yoy_growth_{latest_year}")
                ])
    else:
        year_comparison = pl.DataFrame()
    
    # Prepare burn rate summary
    if include_income:
        burn_rate_summary = pl.DataFrame({
            "metric": ["avg_monthly_income", "avg_monthly_expenses", "net_burn_rate"],
            "value": [avg_monthly_income, avg_monthly_expenses, net_burn_rate]
        })
    else:
        burn_rate_summary = pl.DataFrame({
            "metric": ["avg_monthly_expenses", "gross_burn_rate"],
            "value": [avg_monthly_expenses, avg_monthly_expenses]
        })
    
    return {
        "monthly_trend": monthly_trend,
        "year_comparison": year_comparison,
        "burn_rate": burn_rate_summary
    }


def calculate_category_trend(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    top_n_categories: int = 10
) -> Dict[str, pl.DataFrame]:
    """
    Calculate spending trends by category over time.
    
    Provides:
    - Category spending by month
    - Top growing/declining categories
    - Category share evolution over time
    
    Args:
        df: Transaction DataFrame
        start_date: Optional start date filter
        end_date: Optional end date filter
        top_n_categories: Number of top categories to focus on
        
    Returns:
        Dictionary containing:
        - 'category_by_month': Category spending by month (long format)
        - 'category_pivot': Category spending pivoted by month (wide format)
        - 'category_growth': Category growth rates and trends
        - 'top_growing': Fastest growing categories
        - 'top_declining': Fastest declining categories
    """
    # Prepare and filter data
    df = _prepare_dataframe(df)
    df = _filter_by_date_range(df, start_date, end_date)
    df = _get_expenses_only(df)
    df = _add_temporal_features(df)
    
    if len(df) == 0:
        empty_df = pl.DataFrame()
        return {
            "category_by_month": empty_df,
            "category_pivot": empty_df,
            "category_growth": empty_df,
            "top_growing": empty_df,
            "top_declining": empty_df
        }
    
    # Category spending by month
    category_by_month = df.group_by(["year", "month", "month_name", "category"]).agg([
        pl.col("amount").sum().alias("total_spending"),
        pl.len().alias("transaction_count"),
    ]).sort(["year", "month", "category"])
    
    # Add month total for percentage calculation
    category_by_month = category_by_month.join(
        category_by_month.group_by(["year", "month"]).agg([
            pl.col("total_spending").sum().alias("month_total")
        ]),
        on=["year", "month"],
        how="left"
    ).with_columns([
        (pl.col("total_spending") / pl.col("month_total") * 100).alias("percentage_of_month")
    ])
    
    # Pivot for easier visualization (categories as columns)
    category_pivot = category_by_month.with_columns([
        (pl.col("year").cast(pl.Utf8) + "-" + 
         pl.col("month").cast(pl.Utf8).str.pad_start(2, "0")).alias("year_month")
    ]).pivot(
        values="total_spending",
        index="year_month",
        columns="category"
    ).sort("year_month")
    
    # Category growth analysis
    category_growth = category_by_month.group_by("category").agg([
        pl.col("total_spending").first().alias("first_month_spending"),
        pl.col("total_spending").last().alias("last_month_spending"),
        pl.col("total_spending").sum().alias("total_spending"),
        pl.col("total_spending").mean().alias("avg_monthly_spending"),
        pl.col("total_spending").std().alias("std_dev"),
        pl.len().alias("months_active"),
    ]).with_columns([
        ((pl.col("last_month_spending") - pl.col("first_month_spending")) / 
         pl.col("first_month_spending") * 100).alias("total_growth_pct"),
        (pl.col("std_dev") / pl.col("avg_monthly_spending")).alias("coefficient_of_variation")
    ])
    
    # Top growing and declining categories
    top_growing = category_growth.sort("total_growth_pct", descending=True).head(top_n_categories)
    top_declining = category_growth.sort("total_growth_pct", descending=False).head(top_n_categories)
    
    return {
        "category_by_month": category_by_month,
        "category_pivot": category_pivot,
        "category_growth": category_growth,
        "top_growing": top_growing,
        "top_declining": top_declining
    }


def calculate_merchant_trend(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    top_n_merchants: int = 15,
    min_transactions: int = 3
) -> Dict[str, pl.DataFrame]:
    """
    Calculate spending trends by merchant over time.
    
    Args:
        df: Transaction DataFrame
        start_date: Optional start date filter
        end_date: Optional end date filter
        top_n_merchants: Number of top merchants to analyze
        min_transactions: Minimum transactions for trend analysis
        
    Returns:
        Dictionary containing:
        - 'merchant_by_month': Merchant spending by month
        - 'merchant_trends': Merchant growth and stability metrics
        - 'top_merchants_trend': Top merchants with trend data
    """
    # Prepare and filter data
    df = _prepare_dataframe(df)
    df = _filter_by_date_range(df, start_date, end_date)
    df = _get_expenses_only(df)
    df = _add_temporal_features(df)
    
    if len(df) == 0:
        empty_df = pl.DataFrame()
        return {
            "merchant_by_month": empty_df,
            "merchant_trends": empty_df,
            "top_merchants_trend": empty_df
        }
    
    # Merchant spending by month
    merchant_by_month = df.group_by(["year", "month", "merchant"]).agg([
        pl.col("amount").sum().alias("total_spending"),
        pl.len().alias("transaction_count"),
    ]).sort(["year", "month", "total_spending"], descending=[False, False, True])
    
    # Calculate merchant trends
    merchant_trends = df.group_by("merchant").agg([
        pl.col("amount").sum().alias("total_spending"),
        pl.len().alias("total_transactions"),
        pl.col("amount").mean().alias("avg_transaction"),
        pl.col("amount").std().alias("std_dev"),
        pl.col("date").min().alias("first_transaction"),
        pl.col("date").max().alias("last_transaction"),
    ]).filter(
        pl.col("total_transactions") >= min_transactions
    ).with_columns([
        (pl.col("std_dev") / pl.col("avg_transaction")).alias("spending_volatility")
    ]).sort("total_spending", descending=True)
    
    # Get top merchants and their detailed trends
    top_merchants = merchant_trends.head(top_n_merchants)["merchant"].to_list()
    
    top_merchants_trend = merchant_by_month.filter(
        pl.col("merchant").is_in(top_merchants)
    )
    
    return {
        "merchant_by_month": merchant_by_month,
        "merchant_trends": merchant_trends,
        "top_merchants_trend": top_merchants_trend
    }


def calculate_rolling_averages(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    windows: Optional[List[int]] = None
) -> pl.DataFrame:
    """
    Calculate rolling averages for spending trends.
    
    Args:
        df: Transaction DataFrame
        start_date: Optional start date filter
        end_date: Optional end date filter
        windows: List of window sizes in days (default: [7, 30, 90])
        
    Returns:
        DataFrame with daily spending and rolling averages
    """
    if windows is None:
        windows = [7, 30, 90]
    
    # Prepare and filter data
    df = _prepare_dataframe(df)
    df = _filter_by_date_range(df, start_date, end_date)
    df = _get_expenses_only(df)
    
    if len(df) == 0:
        return pl.DataFrame()
    
    # Aggregate by day
    daily_spending = df.group_by("date").agg([
        pl.col("amount").sum().alias("daily_spending"),
        pl.len().alias("transaction_count"),
    ]).sort("date")
    
    # Fill missing dates with 0 spending
    daily_spending = _fill_missing_dates(
        daily_spending,
        date_col="date",
        value_cols=["daily_spending", "transaction_count"],
        fill_value=0.0
    )
    
    # Calculate rolling averages for each window
    for window in windows:
        daily_spending = daily_spending.with_columns([
            pl.col("daily_spending")
            .rolling_mean(window_size=window)
            .alias(f"rolling_avg_{window}d"),
            pl.col("daily_spending")
            .rolling_std(window_size=window)
            .alias(f"rolling_std_{window}d"),
        ])
    
    # Add additional metrics
    daily_spending = daily_spending.with_columns([
        pl.col("daily_spending").cum_sum().alias("cumulative_spending"),
    ])
    
    return daily_spending


# ============================================================================
# SEASONALITY & CYCLES
# ============================================================================

def analyze_seasonality_simple(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> Dict[str, pl.DataFrame]:
    """
    Analyze seasonal spending patterns using simple aggregation methods.
    
    Provides:
    - Monthly seasonality (average spending by month across years)
    - Quarterly patterns
    - Month-to-month variation
    
    Args:
        df: Transaction DataFrame
        start_date: Optional start date filter
        end_date: Optional end date filter
        
    Returns:
        Dictionary containing:
        - 'monthly_seasonality': Average spending by calendar month
        - 'quarterly_seasonality': Average spending by quarter
        - 'month_volatility': Variation in spending by month
    """
    # Prepare and filter data
    df = _prepare_dataframe(df)
    df = _filter_by_date_range(df, start_date, end_date)
    df = _get_expenses_only(df)
    df = _add_temporal_features(df)
    
    if len(df) == 0:
        empty_df = pl.DataFrame()
        return {
            "monthly_seasonality": empty_df,
            "quarterly_seasonality": empty_df,
            "month_volatility": empty_df
        }
    
    # Calculate overall average for normalization
    overall_avg = df.group_by(["year", "month"]).agg([
        pl.col("amount").sum().alias("monthly_total")
    ])["monthly_total"].mean()
    
    # Monthly seasonality (average across all years)
    monthly_seasonality = df.group_by(["month", "month_name"]).agg([
        pl.col("amount").sum().alias("total_spending"),
        pl.len().alias("transaction_count"),
    ])
    
    # Get count of years per month for proper averaging
    years_per_month = df.group_by("month").agg([
        pl.col("year").n_unique().alias("year_count")
    ])
    
    monthly_seasonality = monthly_seasonality.join(
        years_per_month, on="month", how="left"
    ).with_columns([
        (pl.col("total_spending") / pl.col("year_count")).alias("avg_monthly_spending"),
        (pl.col("transaction_count") / pl.col("year_count")).alias("avg_transactions"),
    ]).with_columns([
        (pl.col("avg_monthly_spending") / overall_avg * 100).alias("seasonality_index"),
    ]).sort("month")
    
    # Quarterly seasonality
    quarterly_seasonality = df.group_by(["quarter"]).agg([
        pl.col("amount").sum().alias("total_spending"),
        pl.len().alias("transaction_count"),
    ])
    
    # Get count of years per quarter
    years_per_quarter = df.group_by("quarter").agg([
        pl.col("year").n_unique().alias("year_count")
    ])
    
    quarterly_seasonality = quarterly_seasonality.join(
        years_per_quarter, on="quarter", how="left"
    ).with_columns([
        (pl.col("total_spending") / pl.col("year_count")).alias("avg_quarterly_spending"),
    ]).sort("quarter")
    
    # Month volatility (how consistent is spending in each month across years)
    month_volatility = df.group_by(["year", "month"]).agg([
        pl.col("amount").sum().alias("monthly_spending")
    ]).group_by("month").agg([
        pl.col("monthly_spending").mean().alias("avg_spending"),
        pl.col("monthly_spending").std().alias("std_dev"),
        pl.len().alias("year_count"),
    ]).with_columns([
        (pl.col("std_dev") / pl.col("avg_spending")).alias("coefficient_of_variation")
    ]).sort("month")
    
    return {
        "monthly_seasonality": monthly_seasonality,
        "quarterly_seasonality": quarterly_seasonality,
        "month_volatility": month_volatility
    }


def analyze_seasonality_advanced(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    period: int = 12,
    model: str = "additive"
) -> Dict[str, Any]:
    """
    Perform advanced seasonal decomposition using statsmodels.
    
    REQUIRES: statsmodels library
    
    Decomposes time series into:
    - Trend component
    - Seasonal component
    - Residual (noise) component
    
    Args:
        df: Transaction DataFrame
        start_date: Optional start date filter
        end_date: Optional end date filter
        period: Seasonal period (12 for monthly, 4 for quarterly)
        model: 'additive' or 'multiplicative'
        
    Returns:
        Dictionary containing:
        - 'trend': Trend component DataFrame
        - 'seasonal': Seasonal component DataFrame
        - 'residual': Residual component DataFrame
        - 'original': Original time series
        - 'seasonal_strength': Metric indicating strength of seasonality
        
    Raises:
        ImportError: If statsmodels is not installed
    """
    
    # Prepare and filter data
    df = _prepare_dataframe(df)
    df = _filter_by_date_range(df, start_date, end_date)
    df = _get_expenses_only(df)
    df = _add_temporal_features(df)
    
    if len(df) == 0:
        return {
            "trend": pl.DataFrame(),
            "seasonal": pl.DataFrame(),
            "residual": pl.DataFrame(),
            "original": pl.DataFrame(),
            "seasonal_strength": 0.0
        }
    
    # Create monthly time series
    monthly_ts = df.group_by(["year", "month"]).agg([
        pl.col("amount").sum().alias("total_spending")
    ]).sort(["year", "month"]).with_columns([
        (pl.col("year").cast(pl.Utf8) + "-" + 
         pl.col("month").cast(pl.Utf8).str.pad_start(2, "0") + "-01").alias("period")
    ])
    
    # Need at least 2 full cycles for decomposition
    min_observations = period * 2
    if len(monthly_ts) < min_observations:
        return {
            "trend": pl.DataFrame(),
            "seasonal": pl.DataFrame(),
            "residual": pl.DataFrame(),
            "original": monthly_ts,
            "seasonal_strength": 0.0,
            "error": f"Insufficient data: need at least {min_observations} observations, have {len(monthly_ts)}"
        }
    
    # Convert to pandas for statsmodels
    import pandas as pd
    ts_pandas = monthly_ts.to_pandas()
    ts_pandas['period'] = pd.to_datetime(ts_pandas['period'])
    ts_pandas = ts_pandas.set_index('period')['total_spending']
    
    # Perform seasonal decomposition
    try:
        decomposition = seasonal_decompose(
            ts_pandas, 
            model=model, 
            period=period,
            extrapolate_trend='freq'
        )
        
        # Convert components back to Polars
        trend_df = pl.DataFrame({
            "period": decomposition.trend.index.strftime("%Y-%m-%d"),
            "trend": decomposition.trend.values
        }).with_columns([
            pl.col("period").str.to_date()
        ])
        
        seasonal_df = pl.DataFrame({
            "period": decomposition.seasonal.index.strftime("%Y-%m-%d"),
            "seasonal": decomposition.seasonal.values
        }).with_columns([
            pl.col("period").str.to_date()
        ])
        
        residual_df = pl.DataFrame({
            "period": decomposition.resid.index.strftime("%Y-%m-%d"),
            "residual": decomposition.resid.values
        }).with_columns([
            pl.col("period").str.to_date()
        ])
        
        # Calculate seasonal strength
        # Seasonal strength = 1 - Var(Residual) / Var(Seasonal + Residual)
        seasonal_var = decomposition.seasonal.var()
        residual_var = decomposition.resid.var()
        seasonal_strength = max(0, 1 - (residual_var / (seasonal_var + residual_var)))
        
        return {
            "trend": trend_df,
            "seasonal": seasonal_df,
            "residual": residual_df,
            "original": monthly_ts,
            "seasonal_strength": seasonal_strength,
            "model": model,
            "period": period
        }
        
    except Exception as e:
        return {
            "trend": pl.DataFrame(),
            "seasonal": pl.DataFrame(),
            "residual": pl.DataFrame(),
            "original": monthly_ts,
            "seasonal_strength": 0.0,
            "error": str(e)
        }


def analyze_day_of_week_patterns(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> Dict[str, pl.DataFrame]:
    """
    Analyze spending patterns by day of week.
    
    Args:
        df: Transaction DataFrame
        start_date: Optional start date filter
        end_date: Optional end date filter
        
    Returns:
        Dictionary containing:
        - 'by_weekday': Spending aggregated by day of week
        - 'weekday_vs_weekend': Comparison of weekday vs weekend spending
        - 'category_by_weekday': Category spending patterns by weekday
    """
    # Prepare and filter data
    df = _prepare_dataframe(df)
    df = _filter_by_date_range(df, start_date, end_date)
    df = _get_expenses_only(df)
    df = _add_temporal_features(df)
    
    if len(df) == 0:
        empty_df = pl.DataFrame()
        return {
            "by_weekday": empty_df,
            "weekday_vs_weekend": empty_df,
            "category_by_weekday": empty_df
        }
    
    # Spending by weekday
    by_weekday = df.group_by(["weekday", "day_name"]).agg([
        pl.col("amount").sum().alias("total_spending"),
        pl.col("amount").mean().alias("avg_transaction"),
        pl.len().alias("transaction_count"),
    ]).sort("weekday")
    
    # Calculate percentage and index
    total_spending = by_weekday["total_spending"].sum()
    daily_avg = total_spending / 7
    
    by_weekday = by_weekday.with_columns([
        (pl.col("total_spending") / total_spending * 100).alias("percentage"),
        (pl.col("total_spending") / daily_avg * 100).alias("day_index"),
    ])
    
    # Weekday vs Weekend comparison
    weekday_vs_weekend = df.with_columns([
        pl.when(pl.col("weekday").is_in([5, 6]))  # Saturday=5, Sunday=6 in Polars
        .then(pl.lit("weekend"))
        .otherwise(pl.lit("weekday"))
        .alias("day_type")
    ]).group_by("day_type").agg([
        pl.col("amount").sum().alias("total_spending"),
        pl.col("amount").mean().alias("avg_transaction"),
        pl.len().alias("transaction_count"),
    ])
    
    # Add per-day averages (weekdays = 5 days, weekend = 2 days)
    weekday_vs_weekend = weekday_vs_weekend.with_columns([
        pl.when(pl.col("day_type") == "weekday")
        .then(pl.col("total_spending") / 5)
        .otherwise(pl.col("total_spending") / 2)
        .alias("avg_per_day")
    ])
    
    # Category spending by weekday
    category_by_weekday = df.group_by(["weekday", "day_name", "category"]).agg([
        pl.col("amount").sum().alias("total_spending"),
        pl.len().alias("transaction_count"),
    ]).sort(["weekday", "total_spending"], descending=[False, True])
    
    return {
        "by_weekday": by_weekday,
        "weekday_vs_weekend": weekday_vs_weekend,
        "category_by_weekday": category_by_weekday
    }


def analyze_payday_proximity(
    df: pl.DataFrame,
    payday_dates: List[int],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    window_days: int = 5
) -> Dict[str, pl.DataFrame]:
    """
    Analyze spending patterns around payday dates.
    
    Args:
        df: Transaction DataFrame
        payday_dates: List of day-of-month for paydays (e.g., [1, 15] for bi-monthly)
        start_date: Optional start date filter
        end_date: Optional end date filter
        window_days: Days before/after payday to analyze
        
    Returns:
        Dictionary containing:
        - 'payday_proximity': Spending by days relative to payday
        - 'payday_summary': Summary statistics around payday
        - 'category_payday_pattern': Category spending patterns relative to payday
    """
    # Prepare and filter data
    df = _prepare_dataframe(df)
    df = _filter_by_date_range(df, start_date, end_date)
    df = _get_expenses_only(df)
    df = _add_temporal_features(df)
    
    if len(df) == 0:
        empty_df = pl.DataFrame()
        return {
            "payday_proximity": empty_df,
            "payday_summary": empty_df,
            "category_payday_pattern": empty_df
        }
    
    # Calculate days from nearest payday
    def days_from_payday(day: int) -> int:
        """Calculate minimum distance to any payday"""
        distances = [abs(day - pd) for pd in payday_dates]
        return min(distances)
    
    df = df.with_columns([
        pl.col("day").map_elements(days_from_payday, return_dtype=pl.Int64).alias("days_from_payday")
    ])
    
    # Classify proximity
    df = df.with_columns([
        pl.when(pl.col("days_from_payday") <= window_days)
        .then(pl.lit("near_payday"))
        .otherwise(pl.lit("between_paydays"))
        .alias("payday_period")
    ])
    
    # Spending by days from payday
    payday_proximity = df.group_by("days_from_payday").agg([
        pl.col("amount").sum().alias("total_spending"),
        pl.col("amount").mean().alias("avg_transaction"),
        pl.len().alias("transaction_count"),
    ]).sort("days_from_payday")
    
    # Summary: near payday vs between paydays
    payday_summary = df.group_by("payday_period").agg([
        pl.col("amount").sum().alias("total_spending"),
        pl.col("amount").mean().alias("avg_transaction"),
        pl.len().alias("transaction_count"),
    ])
    
    # Calculate percentage
    total_spending = payday_summary["total_spending"].sum()
    payday_summary = payday_summary.with_columns([
        (pl.col("total_spending") / total_spending * 100).alias("percentage")
    ])
    
    # Category patterns around payday
    category_payday_pattern = df.group_by(["payday_period", "category"]).agg([
        pl.col("amount").sum().alias("total_spending"),
        pl.len().alias("transaction_count"),
    ]).sort(["payday_period", "total_spending"], descending=[False, True])
    
    return {
        "payday_proximity": payday_proximity,
        "payday_summary": payday_summary,
        "category_payday_pattern": category_payday_pattern
    }


# ============================================================================
# VOLATILITY & STABILITY ANALYTICS
# ============================================================================

def analyze_spending_volatility(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    min_transactions: int = 5
) -> Dict[str, pl.DataFrame]:
    """
    Analyze spending volatility and stability by category.
    
    Provides:
    - Category variance and standard deviation
    - Coefficient of variation (CV) for stability ranking
    - Classification into stable/moderate/volatile categories
    
    Args:
        df: Transaction DataFrame
        start_date: Optional start date filter
        end_date: Optional end date filter
        min_transactions: Minimum transactions for analysis
        
    Returns:
        Dictionary containing:
        - 'category_volatility': Volatility metrics by category
        - 'stable_categories': Most stable spending categories
        - 'volatile_categories': Most volatile spending categories
        - 'monthly_variance': Month-to-month variance by category
    """
    # Prepare and filter data
    df = _prepare_dataframe(df)
    df = _filter_by_date_range(df, start_date, end_date)
    df = _get_expenses_only(df)
    df = _add_temporal_features(df)
    
    if len(df) == 0:
        empty_df = pl.DataFrame()
        return {
            "category_volatility": empty_df,
            "stable_categories": empty_df,
            "volatile_categories": empty_df,
            "monthly_variance": empty_df
        }
    
    # Category volatility (transaction-level)
    category_volatility = df.group_by("category").agg([
        pl.col("amount").mean().alias("mean_transaction"),
        pl.col("amount").std().alias("std_dev"),
        pl.col("amount").var().alias("variance"),
        pl.col("amount").min().alias("min_transaction"),
        pl.col("amount").max().alias("max_transaction"),
        pl.len().alias("transaction_count"),
    ]).filter(
        pl.col("transaction_count") >= min_transactions
    ).with_columns([
        (pl.col("std_dev") / pl.col("mean_transaction")).alias("coefficient_of_variation"),
        (pl.col("max_transaction") - pl.col("min_transaction")).alias("range"),
    ])
    
    # Classify stability
    category_volatility = category_volatility.with_columns([
        pl.when(pl.col("coefficient_of_variation") < 0.3)
        .then(pl.lit("stable"))
        .when(pl.col("coefficient_of_variation") < 0.7)
        .then(pl.lit("moderate"))
        .otherwise(pl.lit("volatile"))
        .alias("stability_class")
    ]).sort("coefficient_of_variation")
    
    # Stable and volatile categories
    stable_categories = category_volatility.filter(
        pl.col("stability_class") == "stable"
    ).sort("mean_transaction", descending=True)
    
    volatile_categories = category_volatility.filter(
        pl.col("stability_class") == "volatile"
    ).sort("coefficient_of_variation", descending=True)
    
    # Monthly variance (how consistent is monthly spending per category)
    monthly_by_category = df.group_by(["year", "month", "category"]).agg([
        pl.col("amount").sum().alias("monthly_spending")
    ])
    
    monthly_variance = monthly_by_category.group_by("category").agg([
        pl.col("monthly_spending").mean().alias("avg_monthly_spending"),
        pl.col("monthly_spending").std().alias("monthly_std_dev"),
        pl.col("monthly_spending").var().alias("monthly_variance"),
        pl.len().alias("months_with_spending"),
    ]).filter(
        pl.col("months_with_spending") >= 3
    ).with_columns([
        (pl.col("monthly_std_dev") / pl.col("avg_monthly_spending")).alias("monthly_cv")
    ]).sort("monthly_variance", descending=True)
    
    return {
        "category_volatility": category_volatility,
        "stable_categories": stable_categories,
        "volatile_categories": volatile_categories,
        "monthly_variance": monthly_variance
    }


def analyze_confidence_adjusted_volatility(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    min_transactions: int = 5
) -> Dict[str, pl.DataFrame]:
    """
    Analyze volatility adjusted by categorization confidence scores.
    
    High confidence + high volatility = truly volatile spending
    Low confidence + high volatility = may be miscategorization
    
    Args:
        df: Transaction DataFrame
        start_date: Optional start date filter
        end_date: Optional end date filter
        min_transactions: Minimum transactions for analysis
        
    Returns:
        Dictionary containing:
        - 'confidence_adjusted': Volatility metrics adjusted by confidence
        - 'high_confidence_volatile': Truly volatile categories (high confidence)
        - 'low_confidence_volatile': Potentially miscategorized volatility
    """
    # Prepare and filter data
    df = _prepare_dataframe(df)
    df = _filter_by_date_range(df, start_date, end_date)
    df = _get_expenses_only(df)
    
    if len(df) == 0:
        empty_df = pl.DataFrame()
        return {
            "confidence_adjusted": empty_df,
            "high_confidence_volatile": empty_df,
            "low_confidence_volatile": empty_df
        }
    
    # Calculate raw and confidence-weighted volatility
    confidence_adjusted = df.with_columns([
        (pl.col("amount") * pl.col("confidence_score")).alias("weighted_amount")
    ]).group_by("category").agg([
        pl.col("amount").mean().alias("raw_mean"),
        pl.col("amount").std().alias("raw_std_dev"),
        pl.col("weighted_amount").mean().alias("weighted_mean"),
        pl.col("weighted_amount").std().alias("weighted_std_dev"),
        pl.col("confidence_score").mean().alias("avg_confidence"),
        pl.len().alias("transaction_count"),
    ]).filter(
        pl.col("transaction_count") >= min_transactions
    ).with_columns([
        (pl.col("raw_std_dev") / pl.col("raw_mean")).alias("raw_cv"),
        (pl.col("weighted_std_dev") / pl.col("weighted_mean")).alias("weighted_cv"),
        ((pl.col("weighted_std_dev") - pl.col("raw_std_dev")) / 
         pl.col("raw_std_dev") * 100).alias("cv_adjustment_pct")
    ])
    
    # High confidence volatile (reliable volatility signal)
    high_confidence_volatile = confidence_adjusted.filter(
        (pl.col("avg_confidence") >= 0.8) &
        (pl.col("raw_cv") >= 0.5)
    ).sort("raw_cv", descending=True)
    
    # Low confidence volatile (may be miscategorization)
    low_confidence_volatile = confidence_adjusted.filter(
        (pl.col("avg_confidence") < 0.6) &
        (pl.col("raw_cv") >= 0.5)
    ).sort("raw_cv", descending=True)
    
    return {
        "confidence_adjusted": confidence_adjusted.sort("raw_cv", descending=True),
        "high_confidence_volatile": high_confidence_volatile,
        "low_confidence_volatile": low_confidence_volatile
    }


def identify_stable_vs_volatile_categories(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    stability_threshold: float = 0.3,
    volatility_threshold: float = 0.7
) -> Dict[str, pl.DataFrame]:
    """
    Classify categories into stable, moderate, and volatile groups.
    
    Args:
        df: Transaction DataFrame
        start_date: Optional start date filter
        end_date: Optional end date filter
        stability_threshold: CV threshold for stable categories
        volatility_threshold: CV threshold for volatile categories
        
    Returns:
        Dictionary containing:
        - 'classification_summary': Count and spending by stability class
        - 'stable': Detailed stable categories
        - 'moderate': Detailed moderate categories
        - 'volatile': Detailed volatile categories
    """
    # Get volatility metrics
    volatility_results = analyze_spending_volatility(
        df=df,
        start_date=start_date,
        end_date=end_date
    )
    
    category_volatility = volatility_results["category_volatility"]
    
    if len(category_volatility) == 0:
        empty_df = pl.DataFrame()
        return {
            "classification_summary": empty_df,
            "stable": empty_df,
            "moderate": empty_df,
            "volatile": empty_df
        }
    
    # Get total spending per category for summary
    df = _prepare_dataframe(df)
    df = _filter_by_date_range(df, start_date, end_date)
    df = _get_expenses_only(df)
    
    category_spending = df.group_by("category").agg([
        pl.col("amount").sum().alias("total_spending")
    ])
    
    category_volatility = category_volatility.join(
        category_spending, on="category", how="left"
    )
    
    # Summary by stability class
    classification_summary = category_volatility.group_by("stability_class").agg([
        pl.len().alias("category_count"),
        pl.col("total_spending").sum().alias("total_spending"),
        pl.col("coefficient_of_variation").mean().alias("avg_cv"),
    ]).sort("category_count", descending=True)
    
    # Separate into classes
    stable = category_volatility.filter(
        pl.col("stability_class") == "stable"
    ).sort("total_spending", descending=True)
    
    moderate = category_volatility.filter(
        pl.col("stability_class") == "moderate"
    ).sort("total_spending", descending=True)
    
    volatile = category_volatility.filter(
        pl.col("stability_class") == "volatile"
    ).sort("coefficient_of_variation", descending=True)
    
    return {
        "classification_summary": classification_summary,
        "stable": stable,
        "moderate": moderate,
        "volatile": volatile
    }


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

def generate_all_temporal_analytics(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    rolling_windows: Optional[List[int]] = None,
    payday_dates: Optional[List[int]] = None,
    top_n_categories: int = 10,
    top_n_merchants: int = 15,
    min_transactions_volatility: int = 5,
    include_advanced_seasonality: bool = False,
    seasonality_period: int = 12,
    seasonality_model: str = "additive"
) -> Dict[str, Any]:
    """
    Generate comprehensive temporal and trend analytics.
    
    This is the main entry point for temporal analytics, providing a complete
    set of time-series, seasonality, and volatility analytics.
    
    Args:
        df: Transaction DataFrame with columns: date, merchant, amount, category, 
            confidence_score, is_recurring
        start_date: Optional start date filter
        end_date: Optional end date filter
        rolling_windows: List of rolling window sizes in days (default: [7, 30, 90])
        payday_dates: List of payday dates (day of month, e.g., [1, 15])
        top_n_categories: Number of top categories for trend analysis
        top_n_merchants: Number of top merchants for trend analysis
        min_transactions_volatility: Minimum transactions for volatility analysis
        include_advanced_seasonality: Whether to use statsmodels for decomposition
        seasonality_period: Period for seasonal decomposition (12=monthly, 4=quarterly)
        seasonality_model: 'additive' or 'multiplicative' for decomposition
        
    Returns:
        Dictionary with keys:
        - 'time_series': Dict of time-series analytics DataFrames
        - 'seasonality': Dict of seasonality analytics DataFrames
        - 'volatility': Dict of volatility analytics DataFrames
        - 'metadata': Dict with generation timestamp and parameters
    """
    # Time-Series Aggregations
    monthly_trend = calculate_monthly_spending_trend(
        df=df,
        start_date=start_date,
        end_date=end_date
    )
    
    category_trend = calculate_category_trend(
        df=df,
        start_date=start_date,
        end_date=end_date,
        top_n_categories=top_n_categories
    )
    
    merchant_trend = calculate_merchant_trend(
        df=df,
        start_date=start_date,
        end_date=end_date,
        top_n_merchants=top_n_merchants
    )
    
    rolling_avg = calculate_rolling_averages(
        df=df,
        start_date=start_date,
        end_date=end_date,
        windows=rolling_windows
    )
    
    # Seasonality & Cycles
    seasonality_simple = analyze_seasonality_simple(
        df=df,
        start_date=start_date,
        end_date=end_date
    )
    
    day_patterns = analyze_day_of_week_patterns(
        df=df,
        start_date=start_date,
        end_date=end_date
    )
    
    # Optional: Advanced seasonality with statsmodels
    seasonality_advanced = None
    if include_advanced_seasonality:
        try:
            seasonality_advanced = analyze_seasonality_advanced(
                df=df,
                start_date=start_date,
                end_date=end_date,
                period=seasonality_period,
                model=seasonality_model
            )
        except ImportError:
            seasonality_advanced = {
                "error": "statsmodels not installed - skipping advanced seasonality"
            }
    
    # Optional: Payday proximity analysis
    payday_analysis = None
    if payday_dates:
        payday_analysis = analyze_payday_proximity(
            df=df,
            payday_dates=payday_dates,
            start_date=start_date,
            end_date=end_date
        )
    
    # Volatility & Stability
    volatility = analyze_spending_volatility(
        df=df,
        start_date=start_date,
        end_date=end_date,
        min_transactions=min_transactions_volatility
    )
    
    confidence_volatility = analyze_confidence_adjusted_volatility(
        df=df,
        start_date=start_date,
        end_date=end_date,
        min_transactions=min_transactions_volatility
    )
    
    stability_classification = identify_stable_vs_volatile_categories(
        df=df,
        start_date=start_date,
        end_date=end_date
    )
    
    # Compile metadata
    df_prepared = _prepare_dataframe(df)
    df_filtered = _filter_by_date_range(df_prepared, start_date, end_date)
    
    metadata = {
        "generated_at": datetime.now().isoformat(),
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "total_transactions": len(df_filtered),
        "date_range": {
            "min": df_filtered["date"].min() if len(df_filtered) > 0 else None,
            "max": df_filtered["date"].max() if len(df_filtered) > 0 else None,
            "days": (df_filtered["date"].max() - df_filtered["date"].min()).days if len(df_filtered) > 0 else 0
        },
        "rolling_windows": rolling_windows or [7, 30, 90],
        "payday_dates": payday_dates,
        "advanced_seasonality_enabled": include_advanced_seasonality
    }
    
    result = {
        "time_series": {
            "monthly_trend": monthly_trend,
            "category_trend": category_trend,
            "merchant_trend": merchant_trend,
            "rolling_averages": rolling_avg
        },
        "seasonality": {
            "simple": seasonality_simple,
            "day_patterns": day_patterns
        },
        "volatility": {
            "spending_volatility": volatility,
            "confidence_adjusted": confidence_volatility,
            "stability_classification": stability_classification
        },
        "metadata": metadata
    }
    
    # Add optional analyses if performed
    if seasonality_advanced:
        result["seasonality"]["advanced"] = seasonality_advanced
    
    if payday_analysis:
        result["seasonality"]["payday"] = payday_analysis
    
    return result
    