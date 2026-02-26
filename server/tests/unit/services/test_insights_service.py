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
    db.add = MagicMock()  # session.add() is sync in SQLAlchemy
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = row
    db.execute.return_value = mock_result
    return db


@pytest.mark.asyncio
async def test_get_insights_returns_cached_row():
    """When a cached row exists and no newer transactions exist, return it without regenerating."""
    from app.services.insights.service import InsightsService

    cached_row = MagicMock()
    db = AsyncMock()
    db.add = MagicMock()

    select_cached = MagicMock()
    select_cached.scalar_one_or_none.return_value = cached_row
    select_max = MagicMock()
    select_max.scalar_one_or_none.return_value = None  # no transactions → no staleness
    db.execute.side_effect = [select_cached, select_max]

    with patch.object(
        InsightsService, "load_and_generate", new_callable=AsyncMock
    ) as mock_gen:
        result = await InsightsService.get_insights(db, "user_123")
        mock_gen.assert_not_awaited()  # no generation triggered

    assert result is cached_row


@pytest.mark.asyncio
async def test_get_insights_generates_when_no_cache():
    """When no cached row exists, get_insights calls load_and_generate then fetches again."""
    from app.services.insights.service import InsightsService

    db = AsyncMock()
    db.add = MagicMock()  # session.add() is sync in SQLAlchemy
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


@pytest.mark.asyncio
async def test_load_and_generate_logs_warning_when_empty():
    """load_and_generate emits a warning when generation returns zero insights."""
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
    ), patch(
        "app.services.insights.service.logger"
    ) as mock_logger:
        await InsightsService.load_and_generate(db, "user_123")

    mock_logger.warning.assert_called_once_with("insights_generated_empty", user_id="user_123")
    mock_logger.info.assert_called_once()  # insights_generated still fires


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
