# Insights: Staleness Detection & Empty-Result Warning Implementation Plan

**Date:** 2026-02-26
**Status:** Implemented  ✓

**Goal:** Fix two bugs in `InsightsService`: add a warning when generation produces zero insights, and regenerate the cache when new transactions exist that post-date it.

**Architecture:** Both changes are isolated to `app/services/insights/service.py`. Fix 1 adds one `logger.warning` call after serialization. Fix 2 adds a `MAX(created_at)` staleness check in `get_insights` before returning the cached row, triggering synchronous regeneration when stale.

**Tech Stack:** SQLAlchemy async, SQLModel, structlog

---

### Task 1: Warn when `load_and_generate` produces zero insights

**Files:**
- Modify: `app/services/insights/service.py:53-54`
- Test: `tests/unit/services/test_insights_service.py`

**Step 1: Write the failing test**

Add this test to `tests/unit/services/test_insights_service.py`:

```python
@pytest.mark.asyncio
async def test_load_and_generate_logs_warning_when_empty(caplog):
    """load_and_generate emits a warning when generation returns zero insights."""
    import logging
    from app.services.insights.service import InsightsService

    db = _mock_db_with_row(None)

    with patch(
        "app.services.insights.service.TransactionService.load_dataframe",
        new_callable=AsyncMock,
        return_value=EMPTY_DF,
    ), patch(
        "app.services.insights.service.generate_insights",
        new_callable=AsyncMock,
        return_value={"formatted_insights": [], "errors": []},
    ):
        with caplog.at_level(logging.WARNING, logger="app.services.insights.service"):
            await InsightsService.load_and_generate(db, "user_123")

    assert any("insights_generated_empty" in r.message for r in caplog.records)
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/services/test_insights_service.py::test_load_and_generate_logs_warning_when_empty -v
```

Expected: FAIL — no warning is currently emitted.

**Step 3: Add the warning log in `service.py`**

In `app/services/insights/service.py`, after the line `serialized = [i.model_dump() for i in formatted_insights]` (currently line 54), add:

```python
if not serialized:
    logger.warning("insights_generated_empty", user_id=user_id)
```

The full block should look like:

```python
formatted_insights = result.get("formatted_insights", [])
serialized = [i.model_dump() for i in formatted_insights]

if not serialized:
    logger.warning("insights_generated_empty", user_id=user_id)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/unit/services/test_insights_service.py::test_load_and_generate_logs_warning_when_empty -v
```

Expected: PASS

**Step 5: Run full service test suite**

```bash
pytest tests/unit/services/test_insights_service.py -v
```

Expected: all tests pass.

**Step 6: Commit**

```bash
git add app/services/insights/service.py tests/unit/services/test_insights_service.py
git commit -m "fix: warn when insights generation returns empty results"
```

---

### Task 2: Invalidate stale insights cache when new transactions exist

**Files:**
- Modify: `app/services/insights/service.py` — `get_insights` method
- Test: `tests/unit/services/test_insights_service.py`

**Step 1: Write the failing tests**

Add these two tests to `tests/unit/services/test_insights_service.py`:

```python
@pytest.mark.asyncio
async def test_get_insights_regenerates_when_stale():
    """When a cached row exists but a newer transaction exists, regenerate."""
    from datetime import UTC, datetime
    from app.services.insights.service import InsightsService

    stale_time = datetime(2024, 1, 1, tzinfo=UTC)
    newer_tx_time = datetime(2024, 6, 1, tzinfo=UTC)

    cached_row = MagicMock()
    cached_row.generated_at = stale_time
    fresh_row = MagicMock()

    db = AsyncMock()
    db.add = MagicMock()

    # execute calls in order:
    # 1. SELECT insight row  → cached_row
    # 2. SELECT MAX(created_at) → newer_tx_time
    # 3. SELECT insight row again (after regen) → fresh_row
    select_cached = MagicMock()
    select_cached.scalar_one_or_none.return_value = cached_row
    select_max = MagicMock()
    select_max.scalar_one_or_none.return_value = newer_tx_time
    select_fresh = MagicMock()
    select_fresh.scalar_one_or_none.return_value = fresh_row
    db.execute.side_effect = [select_cached, select_max, select_fresh]

    with patch.object(
        InsightsService, "load_and_generate", new_callable=AsyncMock
    ) as mock_gen:
        result = await InsightsService.get_insights(db, "user_123")
        mock_gen.assert_awaited_once_with(db, "user_123")

    assert result is fresh_row


@pytest.mark.asyncio
async def test_get_insights_does_not_regenerate_when_fresh():
    """When a cached row is newer than the latest transaction, return it as-is."""
    from datetime import UTC, datetime
    from app.services.insights.service import InsightsService

    newer_cache_time = datetime(2024, 6, 1, tzinfo=UTC)
    older_tx_time = datetime(2024, 1, 1, tzinfo=UTC)

    cached_row = MagicMock()
    cached_row.generated_at = newer_cache_time

    db = AsyncMock()
    db.add = MagicMock()

    select_cached = MagicMock()
    select_cached.scalar_one_or_none.return_value = cached_row
    select_max = MagicMock()
    select_max.scalar_one_or_none.return_value = older_tx_time
    db.execute.side_effect = [select_cached, select_max]

    with patch.object(
        InsightsService, "load_and_generate", new_callable=AsyncMock
    ) as mock_gen:
        result = await InsightsService.get_insights(db, "user_123")
        mock_gen.assert_not_awaited()

    assert result is cached_row
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/services/test_insights_service.py::test_get_insights_regenerates_when_stale tests/unit/services/test_insights_service.py::test_get_insights_does_not_regenerate_when_fresh -v
```

Expected: FAIL — no staleness check exists yet.

**Step 3: Update `get_insights` in `service.py`**

At the top of the file, add `func` to the sqlmodel/sqlalchemy imports:

```python
from sqlmodel import func, select
```

Also import `Transaction` at the top (add after the existing service imports):

```python
from app.models.transaction import Transaction
```

Then replace the `get_insights` method body with:

```python
@staticmethod
async def get_insights(db: AsyncSession, user_id: str) -> InsightModel:
    stmt = select(InsightModel).where(InsightModel.user_id == user_id)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        await InsightsService.load_and_generate(db, user_id)
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
    else:
        # Staleness check: regenerate if any transaction is newer than the cache
        latest_tx_stmt = select(func.max(Transaction.created_at)).where(
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        )
        latest_tx_at = (await db.execute(latest_tx_stmt)).scalar_one_or_none()

        if latest_tx_at and latest_tx_at > row.generated_at:
            await InsightsService.load_and_generate(db, user_id)
            result = await db.execute(stmt)
            row = result.scalar_one_or_none()

    if row is None:
        raise InsightsError("Failed to generate insights for user", user_id=user_id)

    return row
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/services/test_insights_service.py::test_get_insights_regenerates_when_stale tests/unit/services/test_insights_service.py::test_get_insights_does_not_regenerate_when_fresh -v
```

Expected: PASS

**Step 5: Run full service test suite**

```bash
pytest tests/unit/services/test_insights_service.py -v
```

Expected: all tests pass.

**Step 6: Commit**

```bash
git add app/services/insights/service.py tests/unit/services/test_insights_service.py
git commit -m "fix: regenerate insights cache when newer transactions exist"
```

---

### Task 3: Verify integration

**Step 1: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass, no regressions.

**Step 2: Commit if any fixups were needed**

Only needed if step 1 revealed issues. Otherwise, no commit required.
