from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.transaction import CategoryEnum
from app.schemas.transaction import TransactionCreate
from app.services.transaction.service import TransactionService


def make_row(**overrides) -> TransactionCreate:
    base = dict(
        date=datetime(2026, 1, 15, tzinfo=timezone.utc),
        merchant="Netflix",
        amount=Decimal("12.99"),
        category=CategoryEnum.MEDIA_ELECTRONICS,
        description=None,
    )
    return TransactionCreate(**{**base, **overrides})


def make_db(existing_fingerprints: list[str]):
    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = existing_fingerprints
    mock_db.execute = AsyncMock(return_value=mock_result)

    return mock_db


@pytest.mark.asyncio
async def test_import_inserts_all_rows_when_no_duplicates():
    rows = [make_row(merchant="Netflix"), make_row(merchant="Spotify")]
    db = make_db(existing_fingerprints=[])

    imported, skipped, errors = await TransactionService.import_from_csv(db, "user_abc", rows)

    assert imported == 2
    assert skipped == 0
    assert errors == []
    assert db.add.call_count == 2


@pytest.mark.asyncio
async def test_import_skips_rows_with_existing_fingerprints():
    row = make_row(merchant="Netflix")
    existing_fp = TransactionService.compute_fingerprint(
        "user_abc", row.date, row.merchant, row.amount, row.description
    )
    db = make_db(existing_fingerprints=[existing_fp])

    imported, skipped, errors = await TransactionService.import_from_csv(db, "user_abc", [row])

    assert imported == 0
    assert skipped == 1
    assert db.add.call_count == 0


@pytest.mark.asyncio
async def test_import_partial_overlap():
    row_a = make_row(merchant="Netflix")
    row_b = make_row(merchant="Spotify")
    existing_fp = TransactionService.compute_fingerprint(
        "user_abc", row_a.date, row_a.merchant, row_a.amount, row_a.description
    )
    db = make_db(existing_fingerprints=[existing_fp])

    imported, skipped, errors = await TransactionService.import_from_csv(
        db, "user_abc", [row_a, row_b]
    )

    assert imported == 1
    assert skipped == 1


@pytest.mark.asyncio
async def test_import_deduplicates_within_batch():
    """Two identical rows in the same CSV — only one inserted."""
    row = make_row(merchant="Netflix")
    db = make_db(existing_fingerprints=[])

    imported, skipped, errors = await TransactionService.import_from_csv(
        db, "user_abc", [row, row]
    )

    assert imported == 1
    assert skipped == 1
