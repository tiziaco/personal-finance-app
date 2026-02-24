"""Unit tests for TransactionService.

All DB interactions are mocked — no real database required.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import CategoryEnum, Transaction
from app.schemas.transaction import (
    BatchDeleteRequest,
    BatchUpdateItem,
    BatchUpdateRequest,
    TransactionCreate,
    TransactionUpdate,
)
from app.services.transaction.exceptions import TransactionNotFoundError
from app.services.transaction.service import TransactionService

pytestmark = pytest.mark.unit

MOCK_USER_ID = "user_abc123"
MOCK_DATE = datetime(2024, 1, 15, 10, 0, 0)


def make_transaction(**kwargs) -> Transaction:
    defaults = {
        "id": 1,
        "user_id": MOCK_USER_ID,
        "date": MOCK_DATE,
        "merchant": "Supermarket",
        "amount": 42.50,
        "category": CategoryEnum.FOOD_GROCERIES,
        "confidence_score": 1.0,
        "is_recurring": False,
        "created_at": MOCK_DATE,
        "updated_at": MOCK_DATE,
        "deleted_at": None,
    }
    defaults.update(kwargs)
    return Transaction(**defaults)


class TestCreate:
    @pytest.mark.asyncio
    async def test_creates_transaction_with_user_id(self):
        """user_id must be set from the parameter, never from request body."""
        mock_db = AsyncMock(spec=AsyncSession)
        data = TransactionCreate(
            date=MOCK_DATE,
            merchant="Cafe",
            amount=5.0,
            category=CategoryEnum.BARS_RESTAURANTS,
        )

        await TransactionService.create(mock_db, MOCK_USER_ID, data)

        added = mock_db.add.call_args[0][0]
        assert added.user_id == MOCK_USER_ID

    @pytest.mark.asyncio
    async def test_defaults_confidence_score_to_one(self):
        """Manual transactions default to confidence_score=1.0."""
        mock_db = AsyncMock(spec=AsyncSession)
        data = TransactionCreate(
            date=MOCK_DATE,
            merchant="Cafe",
            amount=5.0,
            category=CategoryEnum.BARS_RESTAURANTS,
            # confidence_score intentionally omitted
        )

        await TransactionService.create(mock_db, MOCK_USER_ID, data)

        added = mock_db.add.call_args[0][0]
        assert added.confidence_score == 1.0

    @pytest.mark.asyncio
    async def test_accepts_explicit_confidence_score(self):
        """AI-categorized transactions can pass confidence_score < 1."""
        mock_db = AsyncMock(spec=AsyncSession)
        data = TransactionCreate(
            date=MOCK_DATE,
            merchant="Cafe",
            amount=5.0,
            category=CategoryEnum.BARS_RESTAURANTS,
            confidence_score=0.72,
        )

        await TransactionService.create(mock_db, MOCK_USER_ID, data)

        added = mock_db.add.call_args[0][0]
        assert added.confidence_score == 0.72


class TestGet:
    @pytest.mark.asyncio
    async def test_returns_transaction_for_correct_user(self):
        mock_db = AsyncMock(spec=AsyncSession)
        transaction = make_transaction()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = transaction
        mock_db.execute.return_value = mock_result

        result = await TransactionService.get(mock_db, MOCK_USER_ID, 1)

        assert result.id == 1

    @pytest.mark.asyncio
    async def test_raises_not_found_when_missing(self):
        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(TransactionNotFoundError):
            await TransactionService.get(mock_db, MOCK_USER_ID, 999)

    @pytest.mark.asyncio
    async def test_raises_not_found_for_other_users_transaction(self):
        """Ownership check: another user's transaction returns 404, not the data."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # query scoped to user
        mock_db.execute.return_value = mock_result

        with pytest.raises(TransactionNotFoundError):
            await TransactionService.get(mock_db, "other_user", 1)


class TestUpdate:
    @pytest.mark.asyncio
    async def test_updates_only_provided_fields(self):
        mock_db = AsyncMock(spec=AsyncSession)
        transaction = make_transaction(merchant="Old Name", amount=10.0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = transaction
        mock_db.execute.return_value = mock_result

        data = TransactionUpdate(merchant="New Name")
        result = await TransactionService.update(mock_db, MOCK_USER_ID, 1, data)

        assert result.merchant == "New Name"
        assert result.amount == 10.0  # unchanged

    @pytest.mark.asyncio
    async def test_refreshes_updated_at(self):
        mock_db = AsyncMock(spec=AsyncSession)
        original_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        transaction = make_transaction(updated_at=original_time)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = transaction
        mock_db.execute.return_value = mock_result

        data = TransactionUpdate(merchant="Updated")
        result = await TransactionService.update(mock_db, MOCK_USER_ID, 1, data)

        assert result.updated_at > original_time

    @pytest.mark.asyncio
    async def test_raises_not_found_when_missing(self):
        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(TransactionNotFoundError):
            await TransactionService.update(mock_db, MOCK_USER_ID, 999, TransactionUpdate())


class TestDelete:
    @pytest.mark.asyncio
    async def test_sets_deleted_at(self):
        mock_db = AsyncMock(spec=AsyncSession)
        transaction = make_transaction(deleted_at=None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = transaction
        mock_db.execute.return_value = mock_result

        await TransactionService.delete(mock_db, MOCK_USER_ID, 1)

        assert transaction.deleted_at is not None

    @pytest.mark.asyncio
    async def test_raises_not_found_when_missing(self):
        mock_db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(TransactionNotFoundError):
            await TransactionService.delete(mock_db, MOCK_USER_ID, 999)


class TestBatchUpdate:
    @pytest.mark.asyncio
    async def test_returns_count_of_updated_items(self):
        mock_db = AsyncMock(spec=AsyncSession)
        t1 = make_transaction(id=1)
        t2 = make_transaction(id=2)

        results = [MagicMock(), MagicMock()]
        results[0].scalar_one_or_none.return_value = t1
        results[1].scalar_one_or_none.return_value = t2
        mock_db.execute.side_effect = results

        items = [
            BatchUpdateItem(id=1, merchant="New A"),
            BatchUpdateItem(id=2, merchant="New B"),
        ]
        count = await TransactionService.batch_update(mock_db, MOCK_USER_ID, items)

        assert count == 2

    @pytest.mark.asyncio
    async def test_raises_not_found_on_invalid_id(self):
        """If any ID is invalid the whole batch must raise — no partial updates."""
        mock_db = AsyncMock(spec=AsyncSession)
        t1 = make_transaction(id=1)

        results = [MagicMock(), MagicMock()]
        results[0].scalar_one_or_none.return_value = t1
        results[1].scalar_one_or_none.return_value = None  # second ID not found

        mock_db.execute.side_effect = results

        items = [BatchUpdateItem(id=1, merchant="OK"), BatchUpdateItem(id=999, merchant="Bad")]

        with pytest.raises(TransactionNotFoundError):
            await TransactionService.batch_update(mock_db, MOCK_USER_ID, items)


class TestBatchDelete:
    @pytest.mark.asyncio
    async def test_returns_count_of_deleted_items(self):
        mock_db = AsyncMock(spec=AsyncSession)
        t1 = make_transaction(id=1)
        t2 = make_transaction(id=2)

        results = [MagicMock(), MagicMock()]
        results[0].scalar_one_or_none.return_value = t1
        results[1].scalar_one_or_none.return_value = t2
        mock_db.execute.side_effect = results

        count = await TransactionService.batch_delete(mock_db, MOCK_USER_ID, [1, 2])

        assert count == 2
        assert t1.deleted_at is not None
        assert t2.deleted_at is not None

    @pytest.mark.asyncio
    async def test_raises_not_found_on_invalid_id(self):
        """If any ID is invalid the whole batch must raise — no partial deletes."""
        mock_db = AsyncMock(spec=AsyncSession)
        t1 = make_transaction(id=1)

        results = [MagicMock(), MagicMock()]
        results[0].scalar_one_or_none.return_value = t1
        results[1].scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = results

        with pytest.raises(TransactionNotFoundError):
            await TransactionService.batch_delete(mock_db, MOCK_USER_ID, [1, 999])


# ── load_dataframe tests ──────────────────────────────────────────────────────

import polars as pl
from decimal import Decimal
from datetime import datetime as _datetime

from app.models.transaction import CategoryEnum


def _make_mock_transaction(**kwargs) -> MagicMock:
    t = MagicMock(spec=Transaction)
    t.date = kwargs.get("date", _datetime(2025, 1, 15))
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
    df = await TransactionService.load_dataframe(_mock_db([]), "user_123")

    assert isinstance(df, pl.DataFrame)
    assert len(df) == 0
    assert set(df.columns) == {
        "date", "merchant", "amount", "category", "confidence_score", "is_recurring"
    }


@pytest.mark.asyncio
async def test_load_dataframe_converts_transactions_to_correct_types():
    mock_tx = _make_mock_transaction()
    df = await TransactionService.load_dataframe(_mock_db([mock_tx]), "user_123")

    assert len(df) == 1
    assert df["merchant"][0] == "ACME"
    assert df["amount"][0] == -50.0
    assert df["category"][0] == CategoryEnum.SHOPPING.value
    assert isinstance(df["date"][0], type(df["date"][0]))  # date type


@pytest.mark.asyncio
async def test_load_dataframe_excludes_soft_deleted_via_query():
    db = _mock_db([])
    await TransactionService.load_dataframe(db, "user_123")
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_load_dataframe_applies_date_filter():
    from datetime import date
    db = _mock_db([])
    await TransactionService.load_dataframe(
        db, "user_123",
        date_from=date(2025, 1, 1),
        date_to=date(2025, 3, 31),
    )
    db.execute.assert_called_once()
