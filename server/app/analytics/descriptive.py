"""
Descriptive Analytics Module for Personal Finance App

This module provides comprehensive analytics for transaction data stored in Polars DataFrames.
All methods operate on DataFrames with columns: date, merchant, amount, category, confidence_score, is_recurring

Analytics Categories:
- Spending Overview: Total spending, income vs expenses, averages
- Category Analysis: Spending by category, top categories, frequency analysis
- Merchant Analysis: Top merchants, frequency rankings, one-off vs frequent
- Recurring Transactions: Recurring costs, subscriptions, hidden subscriptions
"""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import date, datetime
import polars as pl


class PeriodEnum(str, Enum):
    """Time period granularity for analytics"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


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


def _separate_income_expenses(df: pl.DataFrame) -> Dict[str, pl.DataFrame]:
    """
    Separate transactions into income and expenses based on amount sign.
    
    Args:
        df: Transaction DataFrame
        
    Returns:
        Dictionary with 'income' and 'expenses' DataFrames
    """
    income = df.filter(pl.col("amount") > 0)
    expenses = df.filter(pl.col("amount") < 0)
    
    # Make expense amounts positive for easier analysis
    expenses = expenses.with_columns([
        pl.col("amount").abs().alias("amount")
    ])
    
    return {
        "income": income,
        "expenses": expenses
    }


def _add_period_columns(df: pl.DataFrame) -> pl.DataFrame:
    """
    Add period grouping columns (year, month, week, day) to DataFrame.
    
    Args:
        df: Transaction DataFrame
        
    Returns:
        DataFrame with additional period columns
    """
    return df.with_columns([
        pl.col("date").dt.year().alias("year"),
        pl.col("date").dt.month().alias("month"),
        pl.col("date").dt.week().alias("week"),
        pl.col("date").dt.day().alias("day"),
    ])


# ============================================================================
# SPENDING OVERVIEW ANALYTICS
# ============================================================================

def calculate_spending_overview(
    df: pl.DataFrame,
    period: PeriodEnum = PeriodEnum.MONTHLY,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> Dict[str, pl.DataFrame]:
    """
    Calculate comprehensive spending overview metrics.
    
    Provides:
    - Total spending per period
    - Income vs expenses breakdown
    - Average transaction amounts
    - Transaction counts per period
    
    Args:
        df: Transaction DataFrame
        period: Time period for aggregation (daily/weekly/monthly/yearly)
        start_date: Optional start date filter
        end_date: Optional end date filter
        
    Returns:
        Dictionary containing:
        - 'summary': Overall statistics DataFrame
        - 'by_period': Period-based aggregation DataFrame
        - 'income_vs_expenses': Income and expense comparison DataFrame
    """
    # Prepare and filter data
    df = _prepare_dataframe(df)
    df = _filter_by_date_range(df, start_date, end_date)
    
    # Separate income and expenses
    separated = _separate_income_expenses(df)
    income_df = separated["income"]
    expenses_df = separated["expenses"]
    
    # Calculate overall summary
    total_income = income_df["amount"].sum() if len(income_df) > 0 else 0.0
    total_expenses = expenses_df["amount"].sum() if len(expenses_df) > 0 else 0.0
    net_amount = total_income - total_expenses
    
    summary = pl.DataFrame({
        "metric": ["total_income", "total_expenses", "net_amount", "total_transactions", "avg_transaction_amount"],
        "value": [
            total_income,
            total_expenses,
            net_amount,
            float(len(df)),
            df["amount"].abs().mean() if len(df) > 0 else 0.0
        ]
    })
    
    # Calculate by period
    df_with_periods = _add_period_columns(df)
    
    # Determine grouping columns based on period
    if period == PeriodEnum.DAILY:
        group_cols = ["year", "month", "day", "date"]
    elif period == PeriodEnum.WEEKLY:
        group_cols = ["year", "week"]
    elif period == PeriodEnum.MONTHLY:
        group_cols = ["year", "month"]
    else:  # YEARLY
        group_cols = ["year"]
    
    # Group and aggregate
    by_period = df_with_periods.group_by(group_cols).agg([
        pl.col("amount").filter(pl.col("amount") > 0).sum().alias("income"),
        pl.col("amount").filter(pl.col("amount") < 0).abs().sum().alias("expenses"),
        pl.len().alias("transaction_count"),
        pl.col("amount").abs().mean().alias("avg_transaction_amount"),
    ]).sort(group_cols)
    
    # Add net amount column
    by_period = by_period.with_columns([
        (pl.col("income") - pl.col("expenses")).alias("net_amount")
    ])
    
    # Calculate income vs expenses comparison
    income_vs_expenses = pl.DataFrame({
        "type": ["income", "expenses"],
        "total_amount": [total_income, total_expenses],
        "transaction_count": [len(income_df), len(expenses_df)],
        "avg_amount": [
            income_df["amount"].mean() if len(income_df) > 0 else 0.0,
            expenses_df["amount"].mean() if len(expenses_df) > 0 else 0.0
        ],
        "percentage": [
            (total_income / (total_income + total_expenses) * 100) if (total_income + total_expenses) > 0 else 0.0,
            (total_expenses / (total_income + total_expenses) * 100) if (total_income + total_expenses) > 0 else 0.0
        ]
    })
    
    return {
        "summary": summary,
        "by_period": by_period,
        "income_vs_expenses": income_vs_expenses
    }


# ============================================================================
# CATEGORY-BASED ANALYTICS
# ============================================================================

def analyze_by_category(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    min_confidence: float = 0.0
) -> Dict[str, pl.DataFrame]:
    """
    Analyze spending patterns by category.
    
    Provides:
    - Spending by category (absolute and percentage)
    - Top categories by total amount
    - Category frequency vs monetary impact
    - Confidence-weighted spending
    
    Args:
        df: Transaction DataFrame
        start_date: Optional start date filter
        end_date: Optional end date filter
        min_confidence: Minimum confidence score (0.0 = include all)
        
    Returns:
        Dictionary containing:
        - 'by_category': Category aggregation DataFrame
        - 'top_categories': Top categories ranked by spending
        - 'frequency_vs_impact': Category frequency and monetary impact
        - 'confidence_weighted': Spending adjusted by confidence scores
    """
    # Prepare and filter data
    df = _prepare_dataframe(df)
    df = _filter_by_date_range(df, start_date, end_date)
    
    # Filter by confidence if specified
    if min_confidence > 0:
        df = df.filter(pl.col("confidence_score") >= min_confidence)
    
    # Focus on expenses for category analysis
    expenses_df = df.filter(pl.col("amount") < 0).with_columns([
        pl.col("amount").abs().alias("amount")
    ])
    
    if len(expenses_df) == 0:
        # Return empty DataFrames if no expenses
        empty_df = pl.DataFrame({
            "category": [],
            "total_amount": [],
            "transaction_count": [],
            "percentage": [],
            "avg_amount": []
        })
        return {
            "by_category": empty_df,
            "top_categories": empty_df,
            "frequency_vs_impact": empty_df,
            "confidence_weighted": empty_df
        }
    
    # Calculate total for percentage
    total_spending = expenses_df["amount"].sum()
    
    # Aggregate by category
    by_category = expenses_df.group_by("category").agg([
        pl.col("amount").sum().alias("total_amount"),
        pl.len().alias("transaction_count"),
        pl.col("amount").mean().alias("avg_amount"),
        pl.col("confidence_score").mean().alias("avg_confidence"),
    ]).sort("total_amount", descending=True)
    
    # Add percentage column
    by_category = by_category.with_columns([
        (pl.col("total_amount") / total_spending * 100).alias("percentage")
    ])
    
    # Top categories (same as by_category but limited)
    top_categories = by_category.head(10)
    
    # Frequency vs impact analysis
    frequency_vs_impact = by_category.select([
        "category",
        "transaction_count",
        "total_amount",
        pl.col("avg_amount").alias("avg_transaction_amount"),
        (pl.col("total_amount") / pl.col("transaction_count")).alias("monetary_impact_per_transaction")
    ]).sort("transaction_count", descending=True)
    
    # Confidence-weighted spending
    confidence_weighted = expenses_df.with_columns([
        (pl.col("amount") * pl.col("confidence_score")).alias("weighted_amount")
    ]).group_by("category").agg([
        pl.col("amount").sum().alias("total_amount"),
        pl.col("weighted_amount").sum().alias("confidence_weighted_amount"),
        pl.col("confidence_score").mean().alias("avg_confidence"),
        pl.len().alias("transaction_count")
    ]).sort("confidence_weighted_amount", descending=True)
    
    # Add adjustment percentage
    confidence_weighted = confidence_weighted.with_columns([
        ((pl.col("confidence_weighted_amount") / pl.col("total_amount") - 1) * 100).alias("adjustment_percentage")
    ])
    
    return {
        "by_category": by_category,
        "top_categories": top_categories,
        "frequency_vs_impact": frequency_vs_impact,
        "confidence_weighted": confidence_weighted
    }


# ============================================================================
# MERCHANT-LEVEL ANALYTICS
# ============================================================================

def analyze_merchants(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    min_frequency_threshold: int = 2,
    top_n: int = 20
) -> Dict[str, pl.DataFrame]:
    """
    Analyze spending patterns by merchant.
    
    Provides:
    - Top merchants by total spending
    - Merchant frequency rankings
    - Average spend per merchant
    - One-off vs frequent merchant classification
    
    Args:
        df: Transaction DataFrame
        start_date: Optional start date filter
        end_date: Optional end date filter
        min_frequency_threshold: Minimum transactions to be considered "frequent"
        top_n: Number of top merchants to return
        
    Returns:
        Dictionary containing:
        - 'top_merchants': Top merchants by spending
        - 'by_frequency': Merchants ranked by transaction frequency
        - 'one_off_vs_frequent': Classification of merchants
        - 'merchant_summary': Complete merchant statistics
    """
    # Prepare and filter data
    df = _prepare_dataframe(df)
    df = _filter_by_date_range(df, start_date, end_date)
    
    # Focus on expenses for merchant analysis
    expenses_df = df.filter(pl.col("amount") < 0).with_columns([
        pl.col("amount").abs().alias("amount")
    ])
    
    if len(expenses_df) == 0:
        empty_df = pl.DataFrame({
            "merchant": [],
            "total_amount": [],
            "transaction_count": [],
            "avg_amount": []
        })
        return {
            "top_merchants": empty_df,
            "by_frequency": empty_df,
            "one_off_vs_frequent": empty_df,
            "merchant_summary": empty_df
        }
    
    # Aggregate by merchant
    merchant_summary = expenses_df.group_by("merchant").agg([
        pl.col("amount").sum().alias("total_amount"),
        pl.len().alias("transaction_count"),
        pl.col("amount").mean().alias("avg_amount"),
        pl.col("amount").min().alias("min_amount"),
        pl.col("amount").max().alias("max_amount"),
        pl.col("date").min().alias("first_transaction"),
        pl.col("date").max().alias("last_transaction"),
    ])
    
    # Add classification
    merchant_summary = merchant_summary.with_columns([
        pl.when(pl.col("transaction_count") >= min_frequency_threshold)
        .then(pl.lit("frequent"))
        .otherwise(pl.lit("one-off"))
        .alias("merchant_type")
    ])
    
    # Top merchants by spending
    top_merchants = merchant_summary.sort("total_amount", descending=True).head(top_n)
    
    # By frequency
    by_frequency = merchant_summary.sort("transaction_count", descending=True).head(top_n)
    
    # One-off vs frequent classification
    one_off_vs_frequent = merchant_summary.group_by("merchant_type").agg([
        pl.len().alias("merchant_count"),
        pl.col("total_amount").sum().alias("total_spending"),
        pl.col("transaction_count").sum().alias("total_transactions"),
        pl.col("avg_amount").mean().alias("avg_transaction_amount"),
    ])
    
    return {
        "top_merchants": top_merchants,
        "by_frequency": by_frequency,
        "one_off_vs_frequent": one_off_vs_frequent,
        "merchant_summary": merchant_summary
    }


# ============================================================================
# RECURRING TRANSACTIONS ANALYTICS
# ============================================================================

def analyze_recurring(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    hidden_subscription_threshold: float = 50.0,
    hidden_subscription_min_frequency: int = 3
) -> Dict[str, pl.DataFrame]:
    """
    Analyze recurring transaction patterns and subscriptions.
    
    Provides:
    - Count of recurring vs non-recurring transactions
    - Monthly recurring costs (subscriptions, rent, utilities)
    - Recurring spending by category
    - Hidden subscriptions detection (low-amount, high-frequency)
    
    Args:
        df: Transaction DataFrame
        start_date: Optional start date filter
        end_date: Optional end date filter
        hidden_subscription_threshold: Maximum amount for hidden subscriptions
        hidden_subscription_min_frequency: Minimum monthly frequency for hidden subscriptions
        
    Returns:
        Dictionary containing:
        - 'recurring_summary': Overview of recurring vs non-recurring
        - 'monthly_recurring_cost': Estimated monthly recurring expenses
        - 'recurring_by_category': Recurring spending breakdown by category
        - 'hidden_subscriptions': Potential undetected subscriptions
    """
    # Prepare and filter data
    df = _prepare_dataframe(df)
    df = _filter_by_date_range(df, start_date, end_date)
    
    # Focus on expenses
    expenses_df = df.filter(pl.col("amount") < 0).with_columns([
        pl.col("amount").abs().alias("amount")
    ])
    
    if len(expenses_df) == 0:
        empty_df = pl.DataFrame()
        return {
            "recurring_summary": empty_df,
            "monthly_recurring_cost": empty_df,
            "recurring_by_category": empty_df,
            "hidden_subscriptions": empty_df
        }
    
    # Recurring vs non-recurring summary
    recurring_summary = expenses_df.group_by("is_recurring").agg([
        pl.len().alias("transaction_count"),
        pl.col("amount").sum().alias("total_amount"),
        pl.col("amount").mean().alias("avg_amount"),
    ])
    
    # Add percentage
    total_transactions = recurring_summary["transaction_count"].sum()
    total_amount = recurring_summary["total_amount"].sum()
    recurring_summary = recurring_summary.with_columns([
        (pl.col("transaction_count") / total_transactions * 100).alias("transaction_percentage"),
        (pl.col("total_amount") / total_amount * 100).alias("amount_percentage"),
    ])
    
    # Monthly recurring cost
    recurring_expenses = expenses_df.filter(pl.col("is_recurring") == True)
    
    if len(recurring_expenses) > 0:
        # Calculate date range in months
        min_date = recurring_expenses["date"].min()
        max_date = recurring_expenses["date"].max()
        
        # Group by merchant to estimate monthly costs
        monthly_recurring_cost = recurring_expenses.group_by("merchant").agg([
            pl.col("amount").sum().alias("total_amount"),
            pl.len().alias("transaction_count"),
            pl.col("amount").mean().alias("avg_transaction_amount"),
            pl.col("date").min().alias("first_transaction"),
            pl.col("date").max().alias("last_transaction"),
            pl.col("category").first().alias("category"),
        ])
        
        # Estimate monthly cost (assuming transactions are roughly evenly distributed)
        monthly_recurring_cost = monthly_recurring_cost.with_columns([
            (pl.col("total_amount") / pl.col("transaction_count")).alias("estimated_monthly_cost")
        ])
    else:
        monthly_recurring_cost = pl.DataFrame({
            "merchant": [],
            "total_amount": [],
            "transaction_count": [],
            "avg_transaction_amount": [],
            "estimated_monthly_cost": [],
            "category": []
        })
    
    # Recurring by category
    recurring_by_category = recurring_expenses.group_by("category").agg([
        pl.col("amount").sum().alias("total_amount"),
        pl.len().alias("transaction_count"),
        pl.col("amount").mean().alias("avg_amount"),
    ]).sort("total_amount", descending=True) if len(recurring_expenses) > 0 else pl.DataFrame()
    
    # Hidden subscriptions detection
    # Find merchants with low amounts, high frequency, but NOT flagged as recurring
    non_recurring = expenses_df.filter(pl.col("is_recurring") == False)
    
    if len(non_recurring) > 0:
        # Add month column for frequency calculation
        non_recurring = non_recurring.with_columns([
            pl.col("date").dt.year().alias("year"),
            pl.col("date").dt.month().alias("month"),
        ])
        
        # Group by merchant and calculate monthly frequency
        hidden_subscriptions = non_recurring.group_by("merchant").agg([
            pl.col("amount").mean().alias("avg_amount"),
            pl.len().alias("total_transactions"),
            pl.col("category").first().alias("category"),
            pl.col("date").min().alias("first_transaction"),
            pl.col("date").max().alias("last_transaction"),
            pl.struct(["year", "month"]).n_unique().alias("months_active"),
        ])
        
        # Calculate monthly frequency
        hidden_subscriptions = hidden_subscriptions.with_columns([
            (pl.col("total_transactions") / pl.col("months_active")).alias("avg_monthly_frequency")
        ])
        
        # Filter for potential hidden subscriptions
        hidden_subscriptions = hidden_subscriptions.filter(
            (pl.col("avg_amount") <= hidden_subscription_threshold) &
            (pl.col("avg_monthly_frequency") >= hidden_subscription_min_frequency)
        ).sort("avg_monthly_frequency", descending=True)
    else:
        hidden_subscriptions = pl.DataFrame()
    
    return {
        "recurring_summary": recurring_summary,
        "monthly_recurring_cost": monthly_recurring_cost,
        "recurring_by_category": recurring_by_category,
        "hidden_subscriptions": hidden_subscriptions
    }


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

def generate_all_analytics(
    df: pl.DataFrame,
    period: PeriodEnum = PeriodEnum.MONTHLY,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    min_confidence: float = 0.0,
    merchant_frequency_threshold: int = 2,
    top_merchants_count: int = 20,
    hidden_subscription_threshold: float = 50.0,
    hidden_subscription_min_frequency: int = 3
) -> Dict[str, Any]:
    """
    Generate comprehensive analytics across all categories.
    
    This is the main entry point for analytics generation, providing a complete
    set of descriptive analytics ready for API consumption.
    
    Args:
        df: Transaction DataFrame with columns: date, merchant, amount, category, 
            confidence_score, is_recurring
        period: Time period for aggregation (daily/weekly/monthly/yearly)
        start_date: Optional start date filter
        end_date: Optional end date filter
        min_confidence: Minimum confidence score for category analysis (0.0 = all)
        merchant_frequency_threshold: Min transactions for "frequent" merchant
        top_merchants_count: Number of top merchants to return
        hidden_subscription_threshold: Max amount for hidden subscription detection
        hidden_subscription_min_frequency: Min monthly frequency for hidden subscriptions
        
    Returns:
        Dictionary with keys:
        - 'spending_overview': Dict of spending overview DataFrames
        - 'category_analysis': Dict of category-based DataFrames
        - 'merchant_analysis': Dict of merchant-level DataFrames
        - 'recurring_analysis': Dict of recurring transaction DataFrames
        - 'metadata': Dict with generation timestamp and parameters
    """
    # Prepare dataframe once for consistent metadata extraction
    df = _prepare_dataframe(df)
    
    # Generate all analytics
    spending_overview = calculate_spending_overview(
        df=df,
        period=period,
        start_date=start_date,
        end_date=end_date
    )
    
    category_analysis = analyze_by_category(
        df=df,
        start_date=start_date,
        end_date=end_date,
        min_confidence=min_confidence
    )
    
    merchant_analysis = analyze_merchants(
        df=df,
        start_date=start_date,
        end_date=end_date,
        min_frequency_threshold=merchant_frequency_threshold,
        top_n=top_merchants_count
    )
    
    recurring_analysis = analyze_recurring(
        df=df,
        start_date=start_date,
        end_date=end_date,
        hidden_subscription_threshold=hidden_subscription_threshold,
        hidden_subscription_min_frequency=hidden_subscription_min_frequency
    )
    
    # Compile metadata
    metadata = {
        "generated_at": datetime.now().isoformat(),
        "period": period.value,
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "min_confidence": min_confidence,
        "total_transactions": len(df),
        "date_range": {
            "min": str(df["date"].min()) if len(df) > 0 else None,
            "max": str(df["date"].max()) if len(df) > 0 else None
        }
    }
    
    return {
        "spending_overview": spending_overview,
        "category_analysis": category_analysis,
        "merchant_analysis": merchant_analysis,
        "recurring_analysis": recurring_analysis,
        "metadata": metadata
    }
