# Analytics Package

Comprehensive analytics module for personal finance transaction analysis. Provides descriptive and temporal analytics with multiple aggregation and decomposition methods.

## Table of Contents

- [Descriptive Analytics](#descriptive-analytics)
- [Temporal Analytics](#temporal-analytics)
- [Data Requirements](#data-requirements)

---

## Descriptive Analytics

Module: `descriptive.py`

### `generate_all_analytics()`

**Main entry point** for comprehensive descriptive analytics across all categories.

Generates spending overview, category analysis, merchant analysis, and recurring transaction patterns. Returns a dictionary with all analytics results and metadata.

**Parameters:**
- `df`: Transaction DataFrame
- `period`: Time aggregation granularity (daily/weekly/monthly/yearly)
- `start_date`, `end_date`: Optional date range filters
- `min_confidence`: Minimum category confidence score (0.0 = all)
- `merchant_frequency_threshold`: Minimum transactions for "frequent" merchant classification
- `top_merchants_count`: Number of top merchants to return
- `hidden_subscription_threshold`: Maximum amount for hidden subscription detection
- `hidden_subscription_min_frequency`: Minimum monthly frequency for subscriptions

### `calculate_spending_overview()`

Calculate comprehensive spending metrics including total spending, income vs expenses, and transaction counts.

**Returns:**
- `summary`: Overall statistics (total income, expenses, net, averages)
- `by_period`: Period-based aggregation
- `income_vs_expenses`: Income and expense breakdown

### `analyze_by_category()`

Analyze spending patterns by category with confidence weighting.

Provides:
- Spending totals and percentages by category
- Top categories ranked by amount
- Frequency vs monetary impact analysis
- Confidence-weighted spending metrics

**Parameters:**
- `min_confidence`: Filter categories by confidence score threshold

### `analyze_merchants()`

Analyze spending patterns by merchant with frequency classification.

Provides:
- Top merchants by total spending
- Merchant ranking by transaction frequency
- One-off vs frequent merchant classification
- Complete merchant statistics

**Parameters:**
- `min_frequency_threshold`: Minimum transactions for "frequent" classification
- `top_n`: Number of top merchants to return

### `analyze_recurring()`

Analyze recurring transactions and detect subscription patterns.

Identifies:
- Recurring vs non-recurring spending breakdown
- Monthly recurring costs and subscriptions
- Recurring spending by category
- Hidden subscriptions (low-amount, high-frequency patterns)

**Parameters:**
- `hidden_subscription_threshold`: Max amount for hidden subscription detection
- `hidden_subscription_min_frequency`: Min monthly frequency for subscriptions

---

## Temporal Analytics

Module: `temporal.py`

### `generate_all_temporal_analytics()`

**Main entry point** for comprehensive temporal and trend analytics.

Generates time-series aggregations, seasonality analysis, and volatility metrics. Returns a dictionary with all temporal analytics results and metadata.

**Parameters:**
- `df`: Transaction DataFrame
- `start_date`, `end_date`: Optional date range filters
- `rolling_windows`: List of window sizes in days (default: [7, 30, 90])
- `payday_dates`: Optional list of payday dates for proximity analysis
- `top_n_categories`: Number of top categories for trend analysis
- `top_n_merchants`: Number of top merchants for trend analysis
- `min_transactions_volatility`: Minimum transactions for volatility analysis
- `include_advanced_seasonality`: Enable statsmodels seasonal decomposition
- `seasonality_period`: Period for decomposition (12=monthly, 4=quarterly)
- `seasonality_model`: 'additive' or 'multiplicative' decomposition

### `calculate_monthly_spending_trend()`

Calculate monthly spending trends with growth rates and burn rate analysis.

Provides:
- Monthly total spending with month-over-month (MoM) growth
- Year-over-year (YoY) comparison
- Cumulative spending metrics
- Burn rate calculations

**Parameters:**
- `include_income`: Include income in trend analysis (default: expenses only)

### `calculate_category_trend()`

Analyze spending trends by category over time.

Provides:
- Category spending by month (long and wide formats)
- Fastest growing categories
- Fastest declining categories
- Category share evolution

**Parameters:**
- `top_n_categories`: Number of top categories to track

### `calculate_merchant_trend()`

Analyze spending trends by merchant over time.

Provides:
- Merchant spending by month
- Merchant growth and stability metrics
- Top merchants with trend data

**Parameters:**
- `top_n_merchants`: Number of top merchants to analyze
- `min_transactions`: Minimum transactions for trend inclusion

### `calculate_rolling_averages()`

Calculate rolling averages for smooth spending trends.

Computes daily spending with multiple rolling window averages for trend smoothing and anomaly detection.

**Parameters:**
- `windows`: List of window sizes in days (default: [7, 30, 90])

### `analyze_seasonality_simple()`

Detect seasonal spending patterns using simple aggregation methods.

Provides:
- Monthly seasonality index (100 = average)
- Quarterly patterns
- Month-to-month variation analysis

No external dependencies required.

### `analyze_seasonality_advanced()`

Perform advanced seasonal decomposition using statsmodels.

**Requires: `statsmodels` library**

Decomposes time series into:
- Trend component
- Seasonal component
- Residual component
- Seasonal strength metric

**Parameters:**
- `period`: Seasonal period (12 for monthly, 4 for quarterly)
- `model`: 'additive' or 'multiplicative' decomposition

### `analyze_day_of_week_patterns()`

Analyze spending patterns by day of week.

Provides:
- Spending aggregated by day of week with indices
- Weekday vs weekend comparison
- Category spending patterns by day

Helps identify behavioral spending patterns across the week.

### `analyze_spending_volatility()`

Analyze spending volatility and stability by category.

Provides:
- Category variance and standard deviation
- Coefficient of variation (CV) for stability ranking
- Classification: stable/moderate/volatile
- Month-to-month variance tracking

**Parameters:**
- `min_transactions`: Minimum transactions for analysis

### `identify_stable_vs_volatile_categories()`

Classify categories into stability groups for budgeting.

Returns:
- Classification summary with category counts and spending
- Detailed stable categories
- Detailed moderate categories
- Detailed volatile categories

Useful for identifying which categories are predictable vs unpredictable.

**Parameters:**
- `stability_threshold`: CV threshold for stable classification
- `volatility_threshold`: CV threshold for volatile classification

---

## Data Requirements

All analytics functions expect a Polars DataFrame with the following columns:

| Column | Type | Description |
|--------|------|-------------|
| `date` | Date | Transaction date (YYYY-MM-DD format) |
| `merchant` | String | Merchant or source name |
| `amount` | Float | Transaction amount (positive=income, negative=expense) |
| `category` | String | Transaction category |
| `confidence_score` | Float | Category confidence (0.0-1.0) |
| `is_recurring` | Boolean | Whether transaction is recurring |

### Data Preparation Example

```python
import polars as pl
from analytics.descriptive import generate_all_analytics
from analytics.temporal import generate_all_temporal_analytics

# Load and prepare data
df = pl.read_csv("transactions.csv")
df = df.with_columns([
    pl.col("date").str.to_date(),
    pl.col("amount").cast(pl.Float64),
    pl.col("confidence_score").cast(pl.Float64),
    pl.col("is_recurring").cast(pl.Boolean),
])

# Generate descriptive analytics
desc_results = generate_all_analytics(df, period="monthly")

# Generate temporal analytics
temp_results = generate_all_temporal_analytics(df, rolling_windows=[7, 30, 90])
```

---

## Analytics Output Structure

Both main functions return nested dictionaries with the following structure:

### Descriptive Analytics Output

```
{
  'spending_overview': {...},      # Spending summaries and overviews
  'category_analysis': {...},      # Category-based breakdowns
  'merchant_analysis': {...},      # Merchant-based breakdowns
  'recurring_analysis': {...},     # Recurring and subscription patterns
  'metadata': {...}                # Generation timestamp and parameters
}
```

### Temporal Analytics Output

```
{
  'time_series': {...},            # Monthly trends, category trends, rolling averages
  'seasonality': {...},            # Monthly, quarterly, and day-of-week patterns
  'volatility': {...},             # Volatility metrics and classifications
  'metadata': {...}                # Generation timestamp and parameters
}
```
