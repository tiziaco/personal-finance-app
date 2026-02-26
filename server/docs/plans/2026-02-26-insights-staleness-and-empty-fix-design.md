# Insights: Staleness Detection & Empty-Result Warning

**Date:** 2026-02-26
**Status:** Approved

## Problem

Two bugs in the insights service:

1. **Silent empty insights** — `generate_insights` catches all graph exceptions and returns
   `{"formatted_insights": []}`. The service stores this empty list without any warning, so
   a failed or data-starved generation is silently cached and served forever.

2. **Stale cache after bulk import** — `GET /insights` always returns the cached row, even
   when new transactions have been added since the cache was built. The CSV upload endpoint
   never invalidates or regenerates insights.

## Design

### Fix 1 — Warn on empty generation result

**File:** `app/services/insights/service.py` — `load_and_generate`

After computing `serialized`, add a warning log when the list is empty:

```python
if not serialized:
    logger.warning("insights_generated_empty", user_id=user_id)
```

No behavior change. The empty list is still persisted and returned. The warning surfaces
silent failures (graph errors, insufficient data) in logs without breaking the API contract.

### Fix 2 — Staleness check on GET /insights

**File:** `app/services/insights/service.py` — `get_insights`

After fetching the cached row (when it exists), compare `row.generated_at` against
`MAX(Transaction.created_at)` for the user. If any transaction is newer than the cache,
regenerate synchronously.

```python
latest_tx_stmt = select(func.max(Transaction.created_at)).where(
    Transaction.user_id == user_id,
    Transaction.deleted_at.is_(None),
)
latest_tx_at = (await db.execute(latest_tx_stmt)).scalar_one_or_none()

if latest_tx_at and latest_tx_at > row.generated_at:
    await InsightsService.load_and_generate(db, user_id)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
```

**Properties:**
- No schema migration required (`Transaction.created_at` already exists via `BaseModel`)
- One extra `MAX(created_at)` query per `GET /insights` call
- Edge case: no transactions → `latest_tx_at` is `None` → check skipped (correct)

## Rejected Alternatives

- **Remove outer try/except in agent.py** — more disruptive, changes error surface
- **Dirty flag on Insight row** — requires schema migration + updating upload endpoint
- **Transaction count comparison** — requires schema migration
- **Background regeneration** — adds task queue complexity for no clear UX benefit
