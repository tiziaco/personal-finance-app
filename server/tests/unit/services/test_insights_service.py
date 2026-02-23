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
