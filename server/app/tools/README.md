# Financial Analytics Tools

Semantic layer providing intent-based tools for finance coach agents. These tools bridge user intents with deterministic analytics computations.

## Available Tools

### 1. `get_spending_summary`
**Intent:** "What is my financial situation?"

Provides overall financial health snapshot.

**Metrics from analytics:**
- `calculate_spending_overview()` - total income, expenses, net, averages
- `calculate_monthly_spending_trend()` - MoM growth, burn rate

---

### 2. `get_category_insights`
**Intent:** "Where does my money go?"

Breaks down spending by category with growth trends.

**Metrics from analytics:**
- `analyze_by_category()` - category totals, percentages, frequency
- `calculate_category_trend()` - category-level MoM trends

---

### 3. `get_recurring_insights`
**Intent:** "What am I locked into?"

Identifies recurring expenses and subscriptions.

**Metrics from analytics:**
- `analyze_recurring()` - recurring vs one-off, monthly costs, hidden subscriptions

---

### 4. `get_trend_insights`
**Intent:** "What changed recently?"

Shows spending changes over time.

**Metrics from analytics:**
- `calculate_monthly_spending_trend()` - MoM/YoY growth, burn rate
- `calculate_category_trend()` - fastest growing/declining categories

---

### 5. `get_behavioral_patterns`
**Intent:** "How do I behave financially?"

Reveals spending habits and patterns.

**Metrics from analytics:**
- `analyze_day_of_week_patterns()` - weekday vs weekend spending
- `analyze_seasonality_simple()` - monthly patterns, seasonal index
- `analyze_spending_volatility()` - stable vs volatile categories

---

### 6. `get_anomaly_insights`
**Intent:** "What looks unusual?"

Detects outliers and abnormal spending.

**Metrics from analytics:**
- `calculate_rolling_averages()` - baseline for anomaly detection
- `analyze_spending_volatility()` - variance and stability metrics
- Custom z-score calculation for outlier transactions

---

### 7. `get_merchant_insights`
**Intent:** "Which merchants control my spending?"

Analyzes spending concentration and merchant patterns.

**Metrics from analytics:**
- `analyze_merchants()` - top merchants, frequency, classification
- Herfindahl index - vendor concentration metric
- One-off vs frequent merchant classification

---

### 8. `get_spending_stability_profile`
**Intent:** "How predictable is my spending?"

Comprehensive spending predictability analysis.

**Metrics from analytics:**
- `identify_stable_vs_volatile_categories()` - stability classification
- `analyze_spending_volatility()` - coefficient of variation per category
- `analyze_recurring()` - recurring vs discretionary split
- `calculate_monthly_spending_trend()` - subscription creep detection

## Usage

```python
from src.tools import ANALYTICAL_TOOLS

# Use with LangGraph agent
agent = create_react_agent(llm, ANALYTICAL_TOOLS)

# Or call directly
import polars as pl
df = pl.read_csv("transactions.csv")
result = await get_spending_summary(df.to_dict())
```

## Design Principles

- **Deterministic:** No LLM reasoning in tools
- **Structured:** Accept/return validated data structures
- **Async:** All tools support async execution
- **Semantic:** Intent-based naming (not implementation details)
