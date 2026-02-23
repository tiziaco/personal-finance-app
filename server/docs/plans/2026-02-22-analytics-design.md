# Analytics Feature Design

**Date:** 2026-02-22
**Status:** Approved

---

## Overview

An analytics layer that bridges existing Polars-based analytics functions to the web application. Exposes seven REST endpoints feeding a dashboard and per-tab analytics page, and leaves the semantic tool layer in a clean state for future agent wiring.

---

## Architecture

Four-layer dependency chain — no circular imports:

```
app/
├── analytics/                        # Layer 1: Pure Polars computation (UNCHANGED)
│   ├── descriptive.py                # generate_all_analytics(df) → Dict
│   └── temporal.py                   # generate_all_temporal_analytics(df) → Dict
│
├── tools/                            # Layer 2: Semantic tools (REFACTORED)
│   └── financial.py                  # 8 intent-based functions: pl.DataFrame in → Dict out
│                                     # Agent-ready: thin LangChain wrappers added later
│
├── services/analytics/               # Layer 3: Data bridge + orchestration (NEW)
│   ├── __init__.py
│   ├── service.py                    # AnalyticsService: load_dataframe + per-domain methods
│   └── exceptions.py                 # AnalyticsError
│
├── schemas/analytics.py              # NEW: request filters + response schemas
│
└── api/v1/
    ├── api.py                        # + analytics_router registered here
    └── analytics.py                  # NEW: 7 GET endpoints
```

**Dependency flow:**
`analytics/` ← `tools/financial.py` ← `services/analytics/service.py` ← `api/v1/analytics.py`

`AnalyticsService` calls `load_dataframe` (DB → Polars), then delegates to the semantic tools in `tools/financial.py`. No analytics logic lives in the router or schemas.

---

## API Endpoints

All routes under `/api/v1/analytics`. Auth required. Rate-limited at **30/minute** (analytics is CPU-heavy). All `GET`.

| Method | Path | Tool(s) called | Description |
|--------|------|----------------|-------------|
| `GET` | `/dashboard` | `get_spending_summary` + `get_category_insights` + `get_recurring_insights` + `get_trend_insights` | Composed summary for the dashboard |
| `GET` | `/spending` | `get_spending_summary` | Spending overview + monthly trend + burn rate |
| `GET` | `/categories` | `get_category_insights` | Category breakdown + top categories + trends |
| `GET` | `/merchants` | `get_merchant_insights` | Top merchants + concentration metrics |
| `GET` | `/recurring` | `get_recurring_insights` + `get_spending_stability_profile` | Subscriptions + hidden subs + stability profile |
| `GET` | `/behavior` | `get_behavioral_patterns` | Day-of-week patterns + seasonality + volatility |
| `GET` | `/anomalies` | `get_anomaly_insights` | Outlier transactions + category spikes |

### Common query params (all endpoints via `AnalyticsFilters`):

```python
class AnalyticsFilters:
    date_from: Optional[date] = Query(None)
    date_to: Optional[date] = Query(None)
```

### Domain-specific params:

| Endpoint | Extra params |
|----------|-------------|
| `/categories` | `top_n: int = Query(10, ge=1, le=50)` |
| `/merchants` | `top_n: int = Query(15, ge=1, le=50)` |
| `/anomalies` | `std_threshold: float = Query(2.5)`, `rolling_window: int = Query(30, ge=7, le=90)` |

---

## Schemas

Analytics responses contain deeply nested Polars output. Response bodies are typed at the envelope level only — not down to every nested key.

```python
class AnalyticsFilters:
    """Common query params injected via Depends() on all endpoints."""
    date_from: Optional[date] = Query(None)
    date_to: Optional[date] = Query(None)

class AnalyticsResponse(BaseModel):
    """Generic envelope for all single-domain endpoints."""
    data: Dict[str, Any]
    generated_at: datetime

class DashboardResponse(BaseModel):
    """Composed response for the dashboard endpoint."""
    spending: Dict[str, Any]
    categories: Dict[str, Any]
    recurring: Dict[str, Any]
    trends: Dict[str, Any]
    generated_at: datetime
```

---

## Service

```python
class AnalyticsService:

    @staticmethod
    async def load_dataframe(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> pl.DataFrame:
        """Fetch non-deleted user transactions from DB and convert to Polars DataFrame.

        Applies date filter at query time (DB-level) for efficiency.
        Returns DataFrame with columns: date, merchant, amount, category,
        confidence_score, is_recurring.
        """

    @staticmethod
    async def get_dashboard(db, user_id, date_from, date_to) -> Dict[str, Any]

    @staticmethod
    async def get_spending(db, user_id, date_from, date_to) -> Dict[str, Any]

    @staticmethod
    async def get_categories(db, user_id, date_from, date_to, top_n) -> Dict[str, Any]

    @staticmethod
    async def get_merchants(db, user_id, date_from, date_to, top_n) -> Dict[str, Any]

    @staticmethod
    async def get_recurring(db, user_id, date_from, date_to) -> Dict[str, Any]

    @staticmethod
    async def get_behavior(db, user_id, date_from, date_to) -> Dict[str, Any]

    @staticmethod
    async def get_anomalies(
        db, user_id, date_from, date_to, std_threshold, rolling_window
    ) -> Dict[str, Any]
```

Each method (except `load_dataframe`) calls `load_dataframe` then the corresponding semantic tool. No analytics logic lives in the service itself.

---

## `tools/financial.py` Refactor

Three changes applied to all 8 functions:

1. `transactions_df: Dict[str, Any]` → `df: pl.DataFrame`
2. `start_date: Optional[str]` / `end_date: Optional[str]` → `Optional[date]`
3. Remove `_validate_and_convert_df`, `_apply_date_filter`, `BaseAnalysisInput/Output` wrappers — functions return `Dict[str, Any]` directly and raise on error

**Before:**
```python
async def get_spending_summary(
    transactions_df: Dict[str, Any],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    success, error, df = _validate_and_convert_df(transactions_df)
    if not success:
        return BaseAnalysisOutput(success=False, error=error).model_dump()
    df = _apply_date_filter(df, start_date, end_date)
    ...
    return BaseAnalysisOutput(success=True, data=result, ...).model_dump()
```

**After:**
```python
async def get_spending_summary(
    df: pl.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    overview = calculate_spending_overview(
        df, period=PeriodEnum.MONTHLY, start_date=start_date, end_date=end_date
    )
    trends = calculate_monthly_spending_trend(
        df, start_date=start_date, end_date=end_date, include_income=True
    )
    ...
    return result  # plain dict, no envelope
```

**Agent draft change:** replace `transactions_df.to_dict()` in state with `transactions_df` (keep as `pl.DataFrame` in state). When wiring LangChain tools later, thin wrappers call `AnalyticsService.load_dataframe` internally via `InjectedToolArg`.

---

## Error Handling

| Scenario | HTTP |
|----------|------|
| Unauthenticated | `401` (existing `AuthMiddleware`) |
| User has no transactions | `200` with empty/zeroed data (analytics functions handle empty DataFrames gracefully) |
| Analytics computation fails | `500` via `AnalyticsError(ServiceError)` → existing `ServiceError` handler |
| Invalid query param (e.g. `date_from` not a date) | `422` (FastAPI validation) |

New exception:
```python
class AnalyticsError(ServiceError):
    error_code = "ANALYTICS_ERROR"
    status_code = 500
```

---

## Testing

### Test Datasets

Located in `tests/data/`:

| File | Contents | Use |
|------|----------|-----|
| `test_transactions_10.csv` | 10 transactions, same month | Thin data, limited category diversity |
| `test_transactions_2_months.csv` | ~90 transactions, 2 months | Boundary for MoM trend functions |
| `test_transactions_400.csv` | ~400 transactions, 3 years | Full analytics pipeline including seasonality |
| *(inline fixture)* | 1 transaction | Edge case: division by zero, empty trends |

CSV files contain `user_id = "test_user"` as a placeholder. Fixtures override this with `test_user.id` (real UUID) at insert time:

```python
@pytest_asyncio.fixture
async def transactions_400(db_session, test_user):
    df = pl.read_csv("tests/data/test_transactions_400.csv")
    for row in df.iter_rows(named=True):
        t = Transaction(
            **{k: v for k, v in row.items() if k != "user_id"},
            user_id=test_user.id,  # override CSV placeholder with real FK
        )
        db_session.add(t)
    await db_session.flush()
```

### Unit Tests — `tests/unit/services/test_analytics_service.py`

No DB. Mock `AsyncSession`. Focused on service behaviour, not analytics math.

| Test | Verifies |
|------|----------|
| `load_dataframe` returns correct columns | `date`, `merchant`, `amount`, `category`, `confidence_score`, `is_recurring` present |
| `load_dataframe` with `date_from`/`date_to` | WHERE clause includes date conditions |
| `load_dataframe` excludes soft-deleted | `deleted_at IS NULL` in query |
| `get_spending` delegates to `get_spending_summary` | Tool called with correct `df`, `start_date`, `end_date` |
| `get_dashboard` composes 4 tools | All 4 keys (`spending`, `categories`, `recurring`, `trends`) present |
| `get_anomalies` forwards `std_threshold` + `rolling_window` | Params forwarded correctly to tool |

### Integration Tests — `tests/integration/api/test_analytics_api.py`

Real DB + `AsyncClient`. Full stack: router → service → DB → tool → response.

| Test | Dataset | Verifies |
|------|---------|----------|
| All 7 endpoints, no auth | — | `401` |
| All 7 endpoints, 0 transactions | — | `200`, valid empty shape |
| `GET /dashboard` | `transactions_400` | All 4 sections populated, `200` |
| `GET /spending` | `transactions_400` | `data` key present, `generated_at` set |
| `GET /categories?top_n=5` | `transactions_10` | At most 5 categories returned |
| `GET /merchants` | `transactions_2_months` | Concentration metrics present |
| `GET /recurring` | `transactions_400` | `hidden_subscriptions` key present |
| `GET /behavior` | `transactions_400` | `day_of_week`, `seasonality`, `volatility` keys present |
| `GET /anomalies?std_threshold=3.0&rolling_window=14` | `transactions_400` | `insights.threshold_std == 3.0` |
| `GET /spending?date_from=X&date_to=Y` | `transactions_400` | Date range respected in `data.date_range` |
| **Edge: 1 transaction** | `transactions_single` | All endpoints return `200` (no 500 from division by zero) |
| **Edge: same-month data** | `transactions_10` | `GET /behavior` returns `200` (no seasonality decomposition error) |
| **Edge: 2-month window** | `transactions_2_months` | `GET /anomalies` returns `200` with thin rolling window data |
