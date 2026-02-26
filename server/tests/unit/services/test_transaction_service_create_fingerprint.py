from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.transaction import TransactionCreate
from app.models.transaction import CategoryEnum
from app.services.transaction.service import TransactionService


@pytest.mark.asyncio
async def test_create_stores_fingerprint():
    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()

    data = TransactionCreate(
        date=datetime(2026, 1, 15, tzinfo=timezone.utc),
        merchant="Netflix",
        amount=Decimal("12.99"),
        category=CategoryEnum.MEDIA_ELECTRONICS,
    )

    added_transaction = None

    def capture_add(obj):
        nonlocal added_transaction
        added_transaction = obj

    mock_db.add = capture_add

    await TransactionService.create(mock_db, "user_abc", data)

    assert added_transaction is not None
    assert added_transaction.fingerprint is not None
    assert len(added_transaction.fingerprint) == 64  # SHA-256 hex


@pytest.mark.asyncio
async def test_create_fingerprint_is_deterministic():
    """Same inputs produce same fingerprint across two calls."""
    data = TransactionCreate(
        date=datetime(2026, 1, 15, tzinfo=timezone.utc),
        merchant="Netflix",
        amount=Decimal("12.99"),
        category=CategoryEnum.MEDIA_ELECTRONICS,
    )

    fingerprints = []
    for _ in range(2):
        mock_db = AsyncMock()
        added = None

        def capture(obj):
            nonlocal added
            added = obj

        mock_db.add = capture
        await TransactionService.create(mock_db, "user_abc", data)
        fingerprints.append(added.fingerprint)

    assert fingerprints[0] == fingerprints[1]
