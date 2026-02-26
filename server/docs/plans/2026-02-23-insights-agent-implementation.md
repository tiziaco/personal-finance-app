# Insights Agent Implementation Plan

**Date:** 2026-02-25
**Status:** Implemented  ✓

**Goal:** Refactor the research-phase insights agent into the app, store results in a DB cache, and expose `GET /api/v1/insights`.

**Architecture:** `TransactionService.load_dataframe` feeds both `AnalyticsService` and `InsightsService`. `InsightsService` calls `generate_insights()` (LangGraph graph), upserts one `Insight` row per user, and serves cached data on every GET. The bulk import endpoint will fire a background task (`asyncio.create_task`) after import — that wiring happens in a future task.

**Tech Stack:** FastAPI, SQLModel, SQLAlchemy (async), Polars, LangGraph, Langfuse (`langfuse.langchain.CallbackHandler`), Alembic, pytest + pytest-asyncio.

---

## Reading list (read these before starting)

- `app/agents/insights/agent.py` — the existing graph to refactor
- `app/services/analytics/service.py` — pattern to follow; `load_dataframe` moves out of here
- `app/services/transaction/service.py` — where `load_dataframe` moves to
- `app/models/base.py` — `BaseModel`, `TimestampMixin`
- `app/models/user.py` — add `insights` relationship here
- `app/models/__init__.py` — export `Insight` here
- `app/agents/shared/observability/langfuse.py` — Langfuse config pattern to copy
- `tests/unit/services/test_analytics_service.py` — unit test style to copy
- `tests/integration/conftest.py` — integration fixtures already defined here

---

## Task 1: Move `load_dataframe` to `TransactionService`

**Why:** `load_dataframe` is a data-access concern (fetch user transactions as a Polars DataFrame). It belongs in `TransactionService`. Both `AnalyticsService` and the upcoming `InsightsService` need it — without this move, `InsightsService` would have to depend on `AnalyticsService` (wrong direction).

**Files:**
- Modify: `app/services/transaction/service.py`
- Modify: `app/services/analytics/service.py`
- Modify: `tests/unit/services/test_analytics_service.py`
- Modify: `tests/unit/services/test_transaction_service.py`

---

**Step 1: Write failing tests for `TransactionService.load_dataframe`**

Open `tests/unit/services/test_transaction_service.py` and add these tests at the end of the file (keep any existing tests):

```python
# ── load_dataframe tests ──────────────────────────────────────────────────────

import polars as pl
import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
from datetime import datetime

from app.models.transaction import CategoryEnum, Transaction


def _make_mock_transaction(**kwargs) -> MagicMock:
    t = MagicMock(spec=Transaction)
    t.date = kwargs.get("date", datetime(2025, 1, 15))
    t.merchant = kwargs.get("merchant", "ACME")
    t.amount = kwargs.get("amount", Decimal("-50.00"))
    t.category = kwargs.get("category", CategoryEnum.SHOPPING)
    t.confidence_score = kwargs.get("confidence_score", 1.0)
    t.is_recurring = kwargs.get("is_recurring", False)
    return t


def _mock_db(transactions: list) -> AsyncMock:
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = transactions
    db.execute.return_value = mock_result
    return db


@pytest.mark.asyncio
async def test_load_dataframe_returns_empty_schema_when_no_transactions():
    from app.services.transaction.service import TransactionService

    df = await TransactionService.load_dataframe(_mock_db([]), "user_123")

    assert isinstance(df, pl.DataFrame)
    assert len(df) == 0
    assert set(df.columns) == {
        "date", "merchant", "amount", "category", "confidence_score", "is_recurring"
    }


@pytest.mark.asyncio
async def test_load_dataframe_converts_transactions_to_correct_types():
    from app.services.transaction.service import TransactionService

    mock_tx = _make_mock_transaction()
    df = await TransactionService.load_dataframe(_mock_db([mock_tx]), "user_123")

    assert len(df) == 1
    assert df["merchant"][0] == "ACME"
    assert df["amount"][0] == -50.0
    assert df["category"][0] == CategoryEnum.SHOPPING.value
    assert isinstance(df["date"][0], type(df["date"][0]))  # date type


@pytest.mark.asyncio
async def test_load_dataframe_excludes_soft_deleted_via_query():
    from app.services.transaction.service import TransactionService

    db = _mock_db([])
    await TransactionService.load_dataframe(db, "user_123")
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_load_dataframe_applies_date_filter():
    from datetime import date
    from app.services.transaction.service import TransactionService

    db = _mock_db([])
    await TransactionService.load_dataframe(
        db, "user_123",
        date_from=date(2025, 1, 1),
        date_to=date(2025, 3, 31),
    )
    db.execute.assert_called_once()
```

**Step 2: Run to verify failure**

```bash
cd /Users/tizianoiacovelli/projects/personal-finance-app/server
pytest tests/unit/services/test_transaction_service.py::test_load_dataframe_returns_empty_schema_when_no_transactions -v
```

Expected: `FAILED` — `AttributeError: type object 'TransactionService' has no attribute 'load_dataframe'`

---

**Step 3: Add `load_dataframe` to `TransactionService`**

Open `app/services/transaction/service.py`. Add these imports at the top (alongside existing ones):

```python
from datetime import date
from typing import Optional
import polars as pl
```

Add this method to `TransactionService` (before the final `transaction_service = TransactionService()` line):

```python
    @staticmethod
    async def load_dataframe(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> pl.DataFrame:
        """Fetch non-deleted user transactions as a typed Polars DataFrame.

        Applies date filter at the DB level for efficiency.
        Returns a typed empty DataFrame (correct schema) when no rows match.

        Args:
            db: Database session.
            user_id: ID of the authenticated user.
            date_from: Optional inclusive start date (DB-level filter).
            date_to: Optional inclusive end date (DB-level filter).

        Returns:
            pl.DataFrame with columns: date (Date), merchant (Utf8),
            amount (Float64), category (Utf8), confidence_score (Float64),
            is_recurring (Boolean).
        """
        from datetime import datetime as dt

        empty_schema = {
            "date": pl.Date,
            "merchant": pl.Utf8,
            "amount": pl.Float64,
            "category": pl.Utf8,
            "confidence_score": pl.Float64,
            "is_recurring": pl.Boolean,
        }

        conditions = [
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        ]
        if date_from:
            conditions.append(Transaction.date >= dt.combine(date_from, dt.min.time()))
        if date_to:
            conditions.append(Transaction.date <= dt.combine(date_to, dt.max.time()))

        stmt = select(Transaction).where(*conditions).order_by(Transaction.date)
        result = await db.execute(stmt)
        transactions = result.scalars().all()

        if not transactions:
            return pl.DataFrame(schema=empty_schema)

        rows = [
            {
                "date": t.date.date() if isinstance(t.date, dt) else t.date,
                "merchant": t.merchant,
                "amount": float(t.amount),
                "category": t.category.value,
                "confidence_score": float(t.confidence_score),
                "is_recurring": t.is_recurring,
            }
            for t in transactions
        ]

        logger.debug(
            "transaction_dataframe_loaded",
            user_id=user_id,
            rows=len(rows),
        )
        return pl.DataFrame(rows)
```

**Step 4: Run transaction service tests**

```bash
pytest tests/unit/services/test_transaction_service.py -v
```

Expected: All `load_dataframe` tests PASS.

---

**Step 5: Update `AnalyticsService` to delegate to `TransactionService`**

Open `app/services/analytics/service.py`.

Replace the `load_dataframe` method body with a delegation call. First add the import at the top:

```python
from app.services.transaction.service import TransactionService
```

Then replace the entire `load_dataframe` staticmethod with:

```python
    @staticmethod
    async def load_dataframe(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> pl.DataFrame:
        """Delegate to TransactionService.load_dataframe.

        Kept here for backwards compatibility — callers in this service
        use self-referential calls (e.g. load_dataframe inside get_spending).
        """
        return await TransactionService.load_dataframe(db, user_id, date_from, date_to)
```

Also remove these imports from `analytics/service.py` that are now owned by `TransactionService` (they were only used in `load_dataframe`):

```python
# REMOVE these if they are no longer used elsewhere in analytics/service.py:
# from sqlmodel import select  ← keep if used in other methods
# from app.models.transaction import Transaction  ← keep if used in other methods
```

Check: `select` and `Transaction` are only used in `load_dataframe` in the analytics service. Since `load_dataframe` now delegates, remove those two imports from `analytics/service.py`.

**Step 6: Update analytics unit tests to mock at the right level**

Open `tests/unit/services/test_analytics_service.py`.

The three tests that call `AnalyticsService.load_dataframe` directly still work (the method still exists). No changes needed for those tests.

**Step 7: Run all unit tests**

```bash
pytest tests/unit/ -v
```

Expected: All PASS.

---

**Step 8: Commit**

```bash
git add app/services/transaction/service.py \
        app/services/analytics/service.py \
        tests/unit/services/test_transaction_service.py
git commit -m "refactor: move load_dataframe to TransactionService"
```

---

## Task 2: Refactor `agents/insights/agent.py`

**Why:** The research-phase agent has broken imports (`from tools.financial` instead of `from app.tools.financial`), serialises the DataFrame to dict unnecessarily, and has no Langfuse observability.

**Files:**
- Modify: `app/agents/insights/agent.py`

**Changes to make (all in one edit pass):**

1. Fix the import block — replace:
   ```python
   from tools.financial import (
       get_spending_summary,
       ...
   )
   ```
   With:
   ```python
   from app.tools.financial import (
       get_spending_summary,
       get_category_insights,
       get_recurring_insights,
       get_trend_insights,
       get_behavioral_patterns,
       get_anomaly_insights,
       get_merchant_insights,
       get_spending_stability_profile,
   )
   ```

2. Add Langfuse imports after existing imports:
   ```python
   from langfuse.langchain import CallbackHandler
   from app.core.config import settings
   ```

3. Change `InsightsState.transactions_df` type annotation:
   ```python
   class InsightsState(TypedDict):
       transactions_df: pl.DataFrame   # was Dict[str, Any]
       ...
   ```

4. In each of the 4 node functions (`analyze_spending_behavior`, `analyze_recurring_patterns`, `analyze_trends_and_stability`, `analyze_behavioral_and_anomalies`), fix the debug logging line that references `.get('shape')`. Replace:
   ```python
   logger.debug(f"... df shape = {state['transactions_df'].get('shape') if isinstance(state['transactions_df'], dict) else 'unknown'}")
   ```
   With:
   ```python
   logger.debug(f"... df shape = {state['transactions_df'].shape}")
   ```
   There are 4 such lines — one per node's `except` block.

5. Add `_create_insights_config` function (add it just before `build_insights_graph`):

   ```python
   def _create_insights_config(user_id: str) -> dict:
       """Create a Langfuse-tagged graph invocation config for the insights agent."""
       return {
           "callbacks": [CallbackHandler()],
           "metadata": {
               "langfuse_user_id": user_id,
               "langfuse_session_id": f"insights-{user_id}",
               "langfuse_tags": ["insights_agent", settings.ENVIRONMENT.value],
           },
       }
   ```

6. Add `user_id: str` parameter to `generate_insights` and update `initial_state` and `ainvoke`:

   Replace:
   ```python
   async def generate_insights(
       transactions_df: pl.DataFrame,
       config: InsightsConfig = None,
       start_date: Optional[str] = None,
       end_date: Optional[str] = None
   ) -> Dict[str, Any]:
   ```
   With:
   ```python
   async def generate_insights(
       transactions_df: pl.DataFrame,
       user_id: str,
       config: InsightsConfig = None,
       start_date: Optional[str] = None,
       end_date: Optional[str] = None
   ) -> Dict[str, Any]:
   ```

7. In `generate_insights`, update `initial_state` — remove `to_dict()`:
   ```python
   initial_state: InsightsState = {
       "transactions_df": transactions_df,   # was transactions_df.to_dict()
       ...
   }
   ```

8. In `generate_insights`, update `ainvoke` to pass Langfuse config:
   ```python
   final_state = await graph.ainvoke(initial_state, config=_create_insights_config(user_id))
   ```

9. Update `generate_insights_sync` to forward `user_id`:
   ```python
   def generate_insights_sync(
       transactions_df: pl.DataFrame,
       user_id: str,
       config: InsightsConfig = None,
       start_date: Optional[str] = None,
       end_date: Optional[str] = None
   ) -> Dict[str, Any]:
       return asyncio.run(
           generate_insights(transactions_df, user_id, config, start_date, end_date)
       )
   ```

**Step 1: Apply all changes above**

**Step 2: Verify imports resolve (no test needed — just a quick smoke check)**

```bash
cd /Users/tizianoiacovelli/projects/personal-finance-app/server
python -c "from app.agents.insights.agent import generate_insights, build_insights_graph; print('OK')"
```

Expected: `OK` printed, no ImportError.

**Step 3: Commit**

```bash
git add app/agents/insights/agent.py
git commit -m "refactor: fix imports, pl.DataFrame state, and Langfuse config in insights agent"
```

---

## Task 3: `Insight` DB model + Alembic migration

**Why:** We need a DB table to cache insights per user.

**Files:**
- Create: `app/models/insight.py`
- Modify: `app/models/user.py`
- Modify: `app/models/__init__.py`
- Create: `alembic/versions/<auto-generated>_add_insight_table.py`

---

**Step 1: Write a failing test to verify the model exists and has correct fields**

Create `tests/unit/models/test_insight_model.py`:

```python
"""Unit tests for the Insight DB model."""


def test_insight_model_has_required_fields():
    from app.models.insight import Insight

    fields = Insight.model_fields
    assert "user_id" in fields
    assert "insights" in fields
    assert "generated_at" in fields


def test_insight_model_is_table():
    from app.models.insight import Insight

    assert hasattr(Insight, "__tablename__")
    assert Insight.__tablename__ == "insight"
```

**Step 2: Run to verify failure**

```bash
pytest tests/unit/models/test_insight_model.py -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'app.models.insight'`

---

**Step 3: Create `app/models/insight.py`**

```python
"""Insight model — cached AI-generated insights per user."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, DateTime
from sqlmodel import Field, Relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class Insight(BaseModel, table=True):
    """Cached AI-generated insights for a user.

    One row per user (unique on user_id). Upserted on every regeneration.
    `insights` stores the serialised List[InsightItem] as JSONB.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True, unique=True)
    insights: list = Field(default_factory=list, sa_type=JSON)
    generated_at: datetime = Field(sa_type=DateTime(timezone=True))

    user: Optional["User"] = Relationship(back_populates="insights")
```

**Step 4: Run model test to verify it passes**

```bash
pytest tests/unit/models/test_insight_model.py -v
```

Expected: PASS.

---

**Step 5: Update `app/models/user.py`**

Add `"Insight"` to the `TYPE_CHECKING` import block at the top:

```python
if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.insight import Insight       # ADD THIS
    from app.models.transaction import Transaction
```

Add the relationship to the `User` class body (after the `transactions` relationship):

```python
    insights: List["Insight"] = Relationship(back_populates="user")
```

Add the avoid-circular-imports import at the bottom of the file (alongside the existing ones):

```python
from app.models.insight import Insight  # noqa: E402   # ADD THIS
```

**Step 6: Update `app/models/__init__.py`**

```python
"""Models package."""

from app.models.conversation import Conversation
from app.models.insight import Insight
from app.models.transaction import CategoryEnum, Transaction
from app.models.user import User

__all__ = [
    "Conversation",
    "Insight",
    "CategoryEnum",
    "Transaction",
    "User",
]
```

**Step 7: Generate the Alembic migration**

```bash
cd /Users/tizianoiacovelli/projects/personal-finance-app/server
alembic revision --autogenerate -m "add_insight_table"
```

This creates a new file in `alembic/versions/`. Open it and verify the `upgrade()` creates:
- Table `insight` with columns: `created_at`, `updated_at`, `id`, `user_id`, `insights` (JSON), `generated_at`
- Index on `user_id`
- UniqueConstraint on `user_id`
- ForeignKey to `user.id`

If anything looks wrong, edit the migration manually before proceeding.

**Step 8: Apply migration (dev DB)**

```bash
alembic upgrade head
```

Expected: `Running upgrade ... -> <new_revision>, add_insight_table`

**Step 9: Commit**

```bash
git add app/models/insight.py \
        app/models/user.py \
        app/models/__init__.py \
        alembic/versions/
git commit -m "feat: add Insight DB model and migration"
```

---

## Task 4: `InsightsError` + `InsightsService` (TDD)

**Files:**
- Create: `app/services/insights/__init__.py`
- Create: `app/services/insights/exceptions.py`
- Create: `tests/unit/services/test_insights_service.py` ← write FIRST
- Create: `app/services/insights/service.py`

---

**Step 1: Write failing unit tests**

Create `tests/unit/services/test_insights_service.py`:

```python
"""Unit tests for InsightsService — mock DB and graph, verify orchestration logic."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import polars as pl
import pytest

EMPTY_DF = pl.DataFrame(
    schema={
        "date": pl.Date,
        "merchant": pl.Utf8,
        "amount": pl.Float64,
        "category": pl.Utf8,
        "confidence_score": pl.Float64,
        "is_recurring": pl.Boolean,
    }
)


def _mock_db_with_row(row):
    """Return an AsyncMock DB that returns `row` from execute().scalar_one_or_none()."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = row
    db.execute.return_value = mock_result
    return db


@pytest.mark.asyncio
async def test_get_insights_returns_cached_row():
    """When a cached row exists, get_insights returns it without triggering generation."""
    from app.services.insights.service import InsightsService

    cached_row = MagicMock()
    db = _mock_db_with_row(cached_row)

    result = await InsightsService.get_insights(db, "user_123")

    assert result is cached_row
    db.execute.assert_called_once()  # only one SELECT, no generation


@pytest.mark.asyncio
async def test_get_insights_generates_when_no_cache():
    """When no cached row exists, get_insights calls load_and_generate then fetches again."""
    from app.services.insights.service import InsightsService

    db = AsyncMock()
    generated_row = MagicMock()

    # First call returns None (no cache), second returns the generated row
    no_cache_result = MagicMock()
    no_cache_result.scalar_one_or_none.return_value = None
    after_gen_result = MagicMock()
    after_gen_result.scalar_one_or_none.return_value = generated_row
    db.execute.side_effect = [no_cache_result, after_gen_result]

    with patch.object(
        InsightsService, "load_and_generate", new_callable=AsyncMock
    ) as mock_gen:
        result = await InsightsService.get_insights(db, "user_123")
        mock_gen.assert_awaited_once_with(db, "user_123")

    assert result is generated_row


@pytest.mark.asyncio
async def test_load_and_generate_upserts_existing_row():
    """When an Insight row already exists, load_and_generate updates it in place."""
    from app.services.insights.service import InsightsService
    from app.models.insight import Insight as InsightModel

    existing_row = MagicMock(spec=InsightModel)
    db = _mock_db_with_row(existing_row)

    with patch(
        "app.services.insights.service.TransactionService.load_dataframe",
        new_callable=AsyncMock,
        return_value=EMPTY_DF,
    ), patch(
        "app.services.insights.service.generate_insights",
        new_callable=AsyncMock,
        return_value={"formatted_insights": [], "errors": []},
    ):
        await InsightsService.load_and_generate(db, "user_123")

    # Existing row was modified and re-added (not a new row)
    assert existing_row.insights == []
    db.add.assert_called_once_with(existing_row)
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_load_and_generate_creates_new_row_when_none_exists():
    """When no Insight row exists, load_and_generate creates one."""
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
        await InsightsService.load_and_generate(db, "user_123")

    db.add.assert_called_once()  # A new InsightModel instance was added
    added_obj = db.add.call_args[0][0]
    assert added_obj.user_id == "user_123"
    assert added_obj.insights == []
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_load_and_generate_with_empty_dataframe_stores_empty_list():
    """Empty DataFrame (new user with no transactions) stores insights: [] without error."""
    from app.services.insights.service import InsightsService

    db = _mock_db_with_row(None)

    with patch(
        "app.services.insights.service.TransactionService.load_dataframe",
        new_callable=AsyncMock,
        return_value=EMPTY_DF,
    ), patch(
        "app.services.insights.service.generate_insights",
        new_callable=AsyncMock,
        return_value={"formatted_insights": [], "errors": ["some warning"]},
    ):
        # Must not raise even with errors in the result
        await InsightsService.load_and_generate(db, "user_123")

    added_obj = db.add.call_args[0][0]
    assert added_obj.insights == []
```

**Step 2: Run to verify failure**

```bash
pytest tests/unit/services/test_insights_service.py -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'app.services.insights'`

---

**Step 3: Create `app/services/insights/__init__.py`**

```python
"""Insights service package."""
```

**Step 4: Create `app/services/insights/exceptions.py`**

```python
"""Insights service domain exceptions."""

from app.exceptions.base import ServiceError


class InsightsError(ServiceError):
    """Raised when insights generation or retrieval fails unexpectedly."""

    error_code = "INSIGHTS_ERROR"
    status_code = 500
```

**Step 5: Create `app/services/insights/service.py`**

```python
"""Insights service — generate, store, and retrieve cached AI insights."""

from datetime import UTC, datetime
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.agents.insights.agent import InsightsConfig, generate_insights
from app.core.logging import logger
from app.models.insight import Insight as InsightModel
from app.services.insights.exceptions import InsightsError
from app.services.llm import llm_service
from app.services.transaction.service import TransactionService


class InsightsService:
    """Stateless insights service.

    Orchestrates: DB fetch → Polars DataFrame → LangGraph insights graph → DB upsert.
    """

    @staticmethod
    async def load_and_generate(db: AsyncSession, user_id: str) -> None:
        """Generate insights and upsert the Insight row for the user.

        Called as a background task after bulk import, or synchronously on
        the first GET when no cached row exists.

        Steps:
        1. Load user transactions as a Polars DataFrame via TransactionService.
        2. Run generate_insights() (LangGraph graph) with LLM enrichment.
        3. Upsert the Insight row (update existing or insert new).

        Args:
            db: Active database session.
            user_id: Authenticated user's ID.

        Raises:
            InsightsError: If the LangGraph graph fails to execute.
        """
        df = await TransactionService.load_dataframe(db, user_id)

        config = InsightsConfig(
            enable_llm_enrichment=True,
            llm_model=llm_service.get_llm(),
        )

        try:
            result = await generate_insights(df, user_id=user_id, config=config)
        except Exception as e:
            raise InsightsError(f"Insights generation failed: {e}") from e

        formatted_insights = result.get("formatted_insights", [])
        serialized = [i.model_dump() for i in formatted_insights]

        # Upsert: update existing row or create a new one
        stmt = select(InsightModel).where(InsightModel.user_id == user_id)
        result_db = await db.execute(stmt)
        existing = result_db.scalar_one_or_none()

        now = datetime.now(UTC)

        if existing:
            existing.insights = serialized
            existing.generated_at = now
            db.add(existing)
        else:
            row = InsightModel(
                user_id=user_id,
                insights=serialized,
                generated_at=now,
            )
            db.add(row)

        await db.flush()

        logger.info(
            "insights_generated",
            user_id=user_id,
            count=len(serialized),
        )

    @staticmethod
    async def get_insights(db: AsyncSession, user_id: str) -> InsightModel:
        """Return the cached Insight row for the user.

        If no row exists yet (first-ever call), generates synchronously first.

        Args:
            db: Active database session.
            user_id: Authenticated user's ID.

        Returns:
            The InsightModel row with insights list and generated_at.

        Raises:
            InsightsError: If generation is triggered and fails.
        """
        stmt = select(InsightModel).where(InsightModel.user_id == user_id)
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None:
            await InsightsService.load_and_generate(db, user_id)
            result = await db.execute(stmt)
            row = result.scalar_one_or_none()

        if row is None:
            raise InsightsError("Failed to generate insights for user", user_id=user_id)

        return row


insights_service = InsightsService()
```

**Step 6: Run unit tests**

```bash
pytest tests/unit/services/test_insights_service.py -v
```

Expected: All 5 tests PASS.

**Step 7: Run full unit suite**

```bash
pytest tests/unit/ -v
```

Expected: All PASS.

**Step 8: Commit**

```bash
git add app/services/insights/ \
        tests/unit/services/test_insights_service.py \
        tests/unit/models/test_insight_model.py
git commit -m "feat: add InsightsService with InsightsError"
```

---

## Task 5: Schemas + `GET /api/v1/insights` endpoint

**Files:**
- Create: `app/schemas/insights.py`
- Create: `app/api/v1/insights.py`
- Modify: `app/api/v1/api.py`

---

**Step 1: Write a failing integration test first**

Create `tests/integration/api/test_insights_api.py` with just the 401 test for now:

```python
"""Integration tests for GET /api/v1/insights."""

import pytest


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_get_insights_unauthenticated(client):
    response = await client.get("/api/v1/insights")
    assert response.status_code == 401
```

Run it:

```bash
pytest tests/integration/api/test_insights_api.py::test_get_insights_unauthenticated -v
```

Expected: `FAILED` — likely `404 Not Found` since the route doesn't exist yet (404 ≠ 401, so the test fails).

---

**Step 2: Create `app/schemas/insights.py`**

```python
"""Schemas for the insights API."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class InsightType(str, Enum):
    SPENDING_BEHAVIOR = "spending_behavior"
    RECURRING_SUBSCRIPTIONS = "recurring_subscriptions"
    TREND = "trend"
    BEHAVIORAL = "behavioral"
    MERCHANT = "merchant"
    STABILITY = "stability"
    ANOMALY = "anomaly"


class SeverityLevel(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class InsightItem(BaseModel):
    """A single AI-generated financial insight."""

    insight_id: str
    type: InsightType
    severity: SeverityLevel
    time_window: str
    summary: str
    narrative_analysis: Optional[str] = None
    supporting_metrics: Dict[str, Any]
    confidence: float
    section: str


class InsightsResponse(BaseModel):
    """Envelope for GET /api/v1/insights."""

    insights: List[InsightItem]
    generated_at: datetime
```

---

**Step 3: Create `app/api/v1/insights.py`**

```python
"""Insights endpoint — serves cached AI-generated financial insights."""

from fastapi import APIRouter, Request

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.database import DbSession
from app.core.limiter import limiter
from app.schemas.insights import InsightItem, InsightsResponse
from app.services.insights.service import insights_service

router = APIRouter()


@router.get(
    "",
    response_model=InsightsResponse,
    summary="Financial insights",
    description=(
        "AI-generated financial insights cached per user. "
        "On first call (no cache), generates synchronously. "
        "Regenerates automatically after bulk transaction import."
    ),
)
@limiter.limit("10/minute")
async def get_insights(
    request: Request,
    db: DbSession,
    user: CurrentUser,
) -> InsightsResponse:
    row = await insights_service.get_insights(db, user.id)
    return InsightsResponse(
        insights=[InsightItem(**i) for i in row.insights],
        generated_at=row.generated_at,
    )
```

---

**Step 4: Register the router in `app/api/v1/api.py`**

Add to the imports:

```python
from app.api.v1.insights import router as insights_router
```

Add to the router registrations:

```python
api_router.include_router(insights_router, prefix="/insights", tags=["insights"])
```

The file should now look like:

```python
"""API v1 router configuration."""

from fastapi import APIRouter

from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chatbot import router as chatbot_router
from app.api.v1.conversation import router as conversation_router
from app.api.v1.insights import router as insights_router
from app.api.v1.transactions import router as transactions_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(conversation_router, prefix="/conversation", tags=["conversation"])
api_router.include_router(chatbot_router, prefix="/chatbot", tags=["chatbot"])
api_router.include_router(transactions_router, prefix="/transactions", tags=["transactions"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
api_router.include_router(insights_router, prefix="/insights", tags=["insights"])
```

---

**Step 5: Run the 401 test**

```bash
pytest tests/integration/api/test_insights_api.py::test_get_insights_unauthenticated -v
```

Expected: PASS (route now exists and returns 401 for unauthenticated requests).

---

**Step 6: Commit**

```bash
git add app/schemas/insights.py \
        app/api/v1/insights.py \
        app/api/v1/api.py \
        tests/integration/api/test_insights_api.py
git commit -m "feat: add GET /api/v1/insights endpoint and schemas"
```

---

## Task 6: Integration tests

**Files:**
- Modify: `tests/integration/api/test_insights_api.py`

Complete the integration test file with all remaining tests:

```python
"""Integration tests for GET /api/v1/insights."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.integration


# ── Auth ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_insights_unauthenticated(client):
    response = await client.get("/api/v1/insights")
    assert response.status_code == 401


# ── Happy path ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_insights_no_transactions_returns_empty(authenticated_client):
    """User with no transactions gets 200 with empty insights list."""
    with patch(
        "app.services.insights.service.generate_insights",
        new_callable=AsyncMock,
        return_value={"formatted_insights": [], "errors": []},
    ):
        response = await authenticated_client.get("/api/v1/insights")

    assert response.status_code == 200
    data = response.json()
    assert data["insights"] == []
    assert "generated_at" in data


@pytest.mark.asyncio
async def test_get_insights_with_transactions_returns_populated(
    authenticated_client, transactions_400
):
    """With 400 transactions, insights list is non-empty."""
    mock_insight = MagicMock()
    mock_insight.model_dump.return_value = {
        "insight_id": "top_spending_category",
        "type": "spending_behavior",
        "severity": "info",
        "time_window": "last_period",
        "summary": "Your top spending category is Bars & Restaurants.",
        "narrative_analysis": None,
        "supporting_metrics": {"category": "Bars & Restaurants", "percentage": 28.5},
        "confidence": 0.95,
        "section": "spending",
    }

    with patch(
        "app.services.insights.service.generate_insights",
        new_callable=AsyncMock,
        return_value={"formatted_insights": [mock_insight], "errors": []},
    ):
        response = await authenticated_client.get("/api/v1/insights")

    assert response.status_code == 200
    data = response.json()
    assert len(data["insights"]) == 1
    assert data["insights"][0]["insight_id"] == "top_spending_category"
    assert data["insights"][0]["section"] == "spending"
    assert "generated_at" in data


# ── Cache behaviour ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_insights_serves_cached_row(
    authenticated_client, db_session, test_user
):
    """Second call serves cached row — generate_insights is never called."""
    from app.models.insight import Insight as InsightModel

    cached = InsightModel(
        user_id=test_user.id,
        insights=[
            {
                "insight_id": "cached_insight",
                "type": "trend",
                "severity": "medium",
                "time_window": "last_3_months",
                "summary": "Spending increased by 12%.",
                "narrative_analysis": None,
                "supporting_metrics": {"mom_growth": 0.12},
                "confidence": 0.88,
                "section": "trends",
            }
        ],
        generated_at=datetime.now(UTC),
    )
    db_session.add(cached)
    await db_session.flush()

    with patch(
        "app.services.insights.service.generate_insights",
        new_callable=AsyncMock,
    ) as mock_gen:
        response = await authenticated_client.get("/api/v1/insights")
        mock_gen.assert_not_awaited()

    assert response.status_code == 200
    data = response.json()
    assert data["insights"][0]["insight_id"] == "cached_insight"


# ── LLM enrichment disabled in tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_insights_narrative_analysis_null_when_llm_disabled(
    authenticated_client, transactions_10
):
    """When LLM enrichment is disabled, narrative_analysis is null."""
    mock_insight = MagicMock()
    mock_insight.model_dump.return_value = {
        "insight_id": "subscription_load_index",
        "type": "recurring_subscriptions",
        "severity": "info",
        "time_window": "monthly",
        "summary": "Recurring expenses account for 15% of spending.",
        "narrative_analysis": None,   # LLM disabled → null
        "supporting_metrics": {"percentage": 15.0},
        "confidence": 0.85,
        "section": "subscriptions",
    }

    with patch(
        "app.services.insights.service.generate_insights",
        new_callable=AsyncMock,
        return_value={"formatted_insights": [mock_insight], "errors": []},
    ):
        response = await authenticated_client.get("/api/v1/insights")

    assert response.status_code == 200
    data = response.json()
    assert data["insights"][0]["narrative_analysis"] is None


# ── Response schema validation ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_insights_response_has_correct_schema(authenticated_client):
    """Response envelope has `insights` list and `generated_at` datetime."""
    with patch(
        "app.services.insights.service.generate_insights",
        new_callable=AsyncMock,
        return_value={"formatted_insights": [], "errors": []},
    ):
        response = await authenticated_client.get("/api/v1/insights")

    assert response.status_code == 200
    data = response.json()
    assert "insights" in data
    assert "generated_at" in data
    assert isinstance(data["insights"], list)
```

**Step 1: Run all integration tests**

```bash
pytest tests/integration/api/test_insights_api.py -v
```

Expected: All 7 tests PASS.

**Step 2: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

**Step 3: Commit**

```bash
git add tests/integration/api/test_insights_api.py
git commit -m "test: add integration tests for insights API"
```

---

## Done

Plan complete and saved to `docs/plans/2026-02-23-insights-agent-implementation.md`.

**Two execution options:**

**1. Subagent-Driven (this session)** — Fresh subagent per task, code review between tasks, fast iteration.

**2. Parallel Session (separate)** — Open a new Claude Code session in this worktree, say *"Use superpowers:executing-plans to implement the plan at `docs/plans/2026-02-23-insights-agent-implementation.md`"*

**Which approach?**
