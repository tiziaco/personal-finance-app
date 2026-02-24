# Insights Agent Design

**Date:** 2026-02-23
**Status:** Approved

---

## Overview

Refactor the research-phase insights agent into the app architecture, wire it to the analytics layer, store results in the database, and expose a single REST endpoint. Insights are generated after bulk CSV import (background task) and served from cache on every subsequent request.

---

## Architecture

```
app/
├── agents/insights/
│   └── agent.py              # REFACTORED: fix imports, pl.DataFrame in state, Langfuse config
│
├── models/
│   └── insight.py            # NEW: Insight table (one row per user, JSONB insights)
│
├── services/
│   ├── transaction/
│   │   └── service.py        # MODIFIED: add load_dataframe() (moved from AnalyticsService)
│   ├── analytics/
│   │   └── service.py        # MODIFIED: call TransactionService.load_dataframe() instead
│   └── insights/             # NEW
│       ├── __init__.py
│       ├── service.py        # InsightsService: load_and_generate + get_insights
│       └── exceptions.py     # InsightsError
│
├── schemas/
│   └── insights.py           # NEW: InsightItem + InsightsResponse
│
└── api/v1/
    ├── api.py                # MODIFIED: register insights_router
    └── insights.py           # NEW: GET /insights
```

**Dependency flow:**

`TransactionService.load_dataframe` ← `InsightsService` ← `api/v1/insights.py`

`agents/insights/agent.py` ← `InsightsService.load_and_generate`

---

## Trigger Strategy

**Primary:** After bulk CSV import succeeds, the import endpoint fires:
```python
asyncio.create_task(InsightsService.load_and_generate(db, user_id))
```
Same pattern as the chatbot's background memory update.

**Fallback:** `GET /api/v1/insights` with no cached row triggers synchronous generation on first call.

**Manual single-add:** Does not trigger regeneration — stale insights are acceptable.

---

## `load_dataframe` Migration

`AnalyticsService.load_dataframe` moves to `TransactionService.load_dataframe` — fetching transactions is TransactionService's domain. Both `AnalyticsService` and `InsightsService` call it independently.

```python
# TransactionService
@staticmethod
async def load_dataframe(
    db: AsyncSession,
    user_id: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> pl.DataFrame:
    """Fetch non-deleted user transactions as a typed Polars DataFrame."""
```

`AnalyticsService` replaces its internal `load_dataframe` with a call to `TransactionService.load_dataframe`.

---

## Agent Refactor (`agents/insights/agent.py`)

Three changes:

1. **Fix imports:** `from tools.financial` → `from app.tools.financial`
2. **Remove dict serialisation:** `transactions_df.to_dict()` → pass `pl.DataFrame` directly in state
3. **Add Langfuse config** with insights-specific tags:

```python
def _create_insights_config(user_id: str) -> dict:
    return {
        "callbacks": [CallbackHandler()],
        "metadata": {
            "langfuse_user_id": user_id,
            "langfuse_session_id": f"insights-{user_id}",
            "langfuse_tags": ["insights_agent", settings.ENVIRONMENT.value],
        },
    }
```

`generate_insights` gains a required `user_id: str` parameter. No checkpointer — the graph is stateless between runs.

---

## DB Model

```python
class Insight(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True, unique=True)

    insights: list[dict] = Field(sa_type=JSON)           # List[InsightItem] serialised
    generated_at: datetime = Field(sa_type=DateTime(timezone=True))

    user: Optional["User"] = Relationship(back_populates="insights")
```

One row per user (`unique=True` on `user_id`). Upserted on every regeneration. `metadata` is omitted — Langfuse captures execution details.

---

## Service

```python
class InsightsService:

    @staticmethod
    async def load_and_generate(db: AsyncSession, user_id: str) -> None:
        """Generate insights from DB and upsert the Insight row.

        Called as a background task after bulk import, or synchronously on
        first GET when no cached row exists.

        1. TransactionService.load_dataframe(db, user_id)
        2. generate_insights(df, user_id, config)
        3. Upsert Insight row (INSERT … ON CONFLICT DO UPDATE)
        """

    @staticmethod
    async def get_insights(db: AsyncSession, user_id: str) -> Insight:
        """Return cached Insight row.

        If no row exists, calls load_and_generate synchronously first.
        Raises InsightsError on generation failure.
        """
```

---

## API Endpoint

**Route:** `GET /api/v1/insights`
**Auth:** Required (existing `AuthMiddleware`)
**Rate limit:** 10/minute

**Response schema:**

```python
class InsightItem(BaseModel):
    insight_id: str
    type: InsightType
    severity: SeverityLevel
    time_window: str
    summary: str
    narrative_analysis: Optional[str]
    supporting_metrics: Dict[str, Any]
    confidence: float
    section: str

class InsightsResponse(BaseModel):
    insights: List[InsightItem]
    generated_at: datetime
```

---

## Langfuse Observability

The insights agent is distinguishable in Langfuse via:

| Field | Value |
|-------|-------|
| `langfuse_session_id` | `f"insights-{user_id}"` |
| `langfuse_tags` | `["insights_agent", "<environment>"]` |
| `langfuse_user_id` | `user_id` |

Filter by tag `insights_agent` in the Langfuse UI to isolate all insights runs from chatbot traces.

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Unauthenticated | `401` (existing `AuthMiddleware`) |
| No insights cached + generation fails | `InsightsError` → `500` |
| No transactions (empty DataFrame) | `200`, `insights: []`, `generated_at` set |
| Partial graph node failure | `200` with partial insights (graceful degradation) |
| LLM enrichment fails per insight | `narrative_analysis: null`, rest of insight intact |

```python
class InsightsError(ServiceError):
    error_code = "INSIGHTS_ERROR"
    status_code = 500
```

---

## Testing

### Unit — `tests/unit/services/test_insights_service.py`

| Test | Verifies |
|------|----------|
| `get_insights` returns cached row | DB read path, no generation triggered |
| `get_insights` no cache → triggers generation | `load_and_generate` called once |
| `load_and_generate` upserts row | existing row updated, not duplicated |
| `load_and_generate` with empty DataFrame | stores `insights: []`, no error |

### Integration — `tests/integration/api/test_insights_api.py`

| Test | Dataset | Verifies |
|------|---------|----------|
| `GET /insights` unauthenticated | — | `401` |
| `GET /insights` no transactions | — | `200`, `insights: []` |
| `GET /insights` with data | `transactions_400` | `200`, insights populated, `generated_at` set |
| `GET /insights` serves cached | `transactions_400` | second call doesn't re-run generation |
| LLM enrichment disabled | `transactions_10` | `narrative_analysis` is `null` |

LLM enrichment is disabled in tests via `InsightsConfig(enable_llm_enrichment=False)` injected through a fixture or monkeypatch.
