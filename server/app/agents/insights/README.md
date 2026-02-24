# Insights Graph

The Insights Graph generates deterministic financial insights from transaction data for dashboard consumption. It analyzes spending patterns (top categories, percentages), recurring subscriptions, temporal trends, behavioral patterns (weekday vs weekend spending, time-of-day habits), merchant concentration, spending stability, and unusual transactions (anomalies). Each insight includes severity levels, confidence scores, and optional LLM-generated narratives for richer context.

## Architecture

```
START 
  ├→ analyze_spending (get_spending_summary + get_category_insights)
  ├→ analyze_recurring (get_recurring_insights)
  ├→ analyze_trends (get_trend_insights + get_spending_stability_profile)
  └→ analyze_behavioral (get_behavioral_patterns + get_merchant_insights + get_anomaly_insights)
       ↓
    [Parallel execution]
       ↓
    aggregate_insights (standardize to Insight schema)
       ↓
    format_insights (template + optional LLM enrichment)
       ↓
    END
```

## Module Structure

```
app/agents/insights/
├── agent.py          # Graph wiring, format_insights, entry points
├── state.py          # InsightsConfig, InsightsState
├── nodes.py          # 4 async analyze_* functions
├── aggregator.py     # aggregate_insights
├── templates.py      # INSIGHT_TEMPLATES (deterministic summaries)
└── prompts/
    ├── __init__.py   # load_narrative_prompt(version)
    └── v1.md         # LLM narrative prompt (add v2.md, etc. for evals)
```

## Basic Usage

### Async (Recommended)

```python
import polars as pl
from app.agents.insights import generate_insights, InsightsConfig

# Load transactions
df = pl.read_csv("transactions.csv")

# Generate insights with defaults (templates only)
result = await generate_insights(
    df,
    user_id="user_123",
    config=InsightsConfig(enable_llm_enrichment=False)
)

# Access results
for insight in result["formatted_insights"]:
    print(f"[{insight.severity}] {insight.summary}")
    print(f"  Section: {insight.section}")
    print(f"  Confidence: {insight.confidence}")
```

### Sync (For Django/FastAPI)

```python
from app.agents.insights import generate_insights_sync

# Blocking call - suitable for request handlers
result = generate_insights_sync(df, user_id="user_123")

# Use in your dashboard API
return {
    "insights": [i.model_dump() for i in result["formatted_insights"]],
    "metadata": result["metadata"]
}
```

## With LLM Enrichment

```python
from langchain_openai import ChatOpenAI
from app.agents.insights import generate_insights, InsightsConfig

llm = ChatOpenAI(model="gpt-4-turbo")

config = InsightsConfig(
    enable_llm_enrichment=True,
    llm_model=llm
)

result = await generate_insights(df, user_id="user_123", config=config)

# Now each insight has optional narrative_analysis
for insight in result["formatted_insights"]:
    print(f"{insight.summary}\n")
    if insight.narrative_analysis:
        print(f"💡 {insight.narrative_analysis}\n")
```

## Configuration Options

```python
config = InsightsConfig(
    enable_llm_enrichment=False,        # Toggle LLM narratives
    llm_model=None,                     # LLM instance if enabled
    time_window_days=90,                # Default analysis period
    min_confidence_score=0.7,           # Minimum confidence threshold
    include_anomalies=True,             # Include anomaly detection
    anomaly_std_threshold=2.5,          # Std deviations for anomalies
    narrative_prompt_version="v1",      # Prompt version for LLM narratives
)
```

## Insight Schema

Each insight returned has this structure:

```python
Insight(
    insight_id="top_spending_category",          # Unique ID
    type=InsightType.SPENDING_BEHAVIOR,          # Category
    severity=SeverityLevel.INFO,                 # info|low|medium|high|critical
    time_window="last_period",                   # Analysis period
    summary="Your top spending category...",     # Templated (deterministic)
    narrative_analysis="This means...",          # Optional (LLM-generated)
    supporting_metrics={                         # Raw data
        "category": "Food & Groceries",
        "percentage": 28.5,
        "amount": 1450.00
    },
    confidence=0.95,                             # 0.0-1.0
    section="spending"                           # Dashboard section
)
```


## Insight Types

| Type | Intent | Section |
|------|--------|---------|
| `SPENDING_BEHAVIOR` | Where does my money go? | spending |
| `RECURRING_SUBSCRIPTIONS` | What am I locked into? | subscriptions |
| `TREND` | What changed recently? | trends |
| `BEHAVIORAL` | How do I behave? | behavior |
| `MERCHANT` | Which merchants control my spending? | anomalies |
| `STABILITY` | How predictable is my spending? | trends |
| `ANOMALY` | What looks unusual? | anomalies |

## Performance

- **Execution time**: Typically 2-5 seconds (parallel tool execution)
- **With LLM enrichment**: Add 1-2s per insight for LLM API calls
- **Memory**: ~100MB for typical 10K transaction datasets

## Error Handling

Insights graph uses graceful degradation:

```python
result = await generate_insights(df)

# Check for errors
if result["errors"]:
    print(f"Warnings: {result['errors']}")
    # Still has partial insights from successful analyses

# Access metadata
print(f"Generated {result['metadata']['total_insights']} insights")
print(f"Execution time: {result['metadata']['execution_time_seconds']}s")
```

## Advanced: Custom Template Modifications

To customize deterministic insight summaries, modify `INSIGHT_TEMPLATES` in `templates.py`:

```python
from app.agents.insights.templates import INSIGHT_TEMPLATES
from app.schemas.insights import InsightType

INSIGHT_TEMPLATES[InsightType.SPENDING_BEHAVIOR]["top_category"] = \
    "You're spending {percentage}% on {category} - that's {amount_formatted}!"
```

## Advanced: Prompt Versioning for Evals

To test a new LLM narrative prompt, add a new markdown file in `prompts/` and pass the version via config:

```python
# 1. Create prompts/v2.md with your new prompt template
# 2. Run with the new version
config = InsightsConfig(
    enable_llm_enrichment=True,
    llm_model=llm,
    narrative_prompt_version="v2",
)
result = await generate_insights(df, user_id="user_123", config=config)
```

The prompt file uses flat named placeholders: `{insight_type}`, `{summary}`, `{metrics}`.

## Next Steps

- Store insights in database for historical tracking
- Build alerts on specific insight types/severities
- Create recommendation engine that consumes insights
- Integrate with Financial Coach agent for personalized advice
