# Transactions CRUD Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement full CRUD for financial transactions — single + batch — with a paginated, filterable GET endpoint, soft delete, and TDD coverage.

**Architecture:** Stateless `TransactionService` with `@staticmethod` async methods, a rate-limited FastAPI router under `/api/v1/transactions`, and Pydantic schemas for request/response validation. Soft delete via `SoftDeleteMixin` (`deleted_at`). Batch operations are all-or-nothing (DB transaction rollback on any failure).

**Tech Stack:** FastAPI, SQLModel, SQLAlchemy async (`AsyncSession`), PostgreSQL, pytest + pytest-asyncio, Alembic.

---

## Reference files (read before starting each task)

- `app/models/base.py` — `BaseModel`, `SoftDeleteMixin`, `TimestampMixin`
- `app/models/user.py` — User model (need to add `transactions` relationship)
- `app/services/conversation/service.py` — service pattern to follow
- `app/services/conversation/exceptions.py` — exception pattern
- `app/api/v1/conversation.py` — router pattern (rate limiting, deps, docstrings)
- `app/api/v1/api.py` — where to register the new router
- `app/api/dependencies/auth.py` — `CurrentUser` type alias
- `app/api/dependencies/database.py` — `DbSession` type alias, `get_db_session`
- `app/core/config.py` — rate limit config structure
- `tests/conftest.py` — shared fixtures
- `tests/unit/` and `tests/integration/` — test structure

---

## Task 1: CategoryEnum + Transaction model

**Files:**
- Create: `app/models/transaction.py`
- Modify: `app/models/user.py` (add `transactions` relationship)
- Modify: `app/models/__init__.py` (export `Transaction`, `CategoryEnum`)

**Step 1: Create `app/models/transaction.py`**

```python
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.user import User


class CategoryEnum(str, Enum):
    """Predefined spending categories for transaction classification."""

    INCOME = "Income"
    TRANSPORTATION = "Transportation"
    SALARY = "Salary"
    HOUSEHOLD_UTILITIES = "Household & Utilities"
    TAX_FINES = "Tax & Fines"
    MISCELLANEOUS = "Miscellaneous"
    FOOD_GROCERIES = "Food & Groceries"
    FOOD_DELIVERY = "Food Delivery"
    ATM = "ATM"
    INSURANCE = "Insurances"
    SHOPPING = "Shopping"
    BARS_RESTAURANTS = "Bars & Restaurants"
    EDUCATION = "Education"
    FAMILY_FRIENDS = "Family & Friends"
    DONATIONS_CHARITY = "Donations & Charity"
    HEALTHCARE_DRUG_STORES = "Healthcare & Drug Stores"
    LEISURE_ENTERTAINMENT = "Leisure & Entertainment"
    MEDIA_ELECTRONICS = "Media & Electronics"
    SAVINGS_INVESTMENTS = "Savings & Investments"
    TRAVEL_HOLIDAYS = "Travel & Holidays"


class Transaction(SQLModel, SoftDeleteMixin, table=True):
    """Financial transaction record owned by a user.

    confidence_score=1.0 signals a manually-entered (human-verified) transaction.
    Soft-deleted records (deleted_at IS NOT NULL) are excluded from all queries.
    """

    # Primary & Foreign Keys
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)

    # Core Transaction Data
    date: datetime = Field(index=True)
    merchant: str
    amount: float
    description: Optional[str] = None
    original_category: Optional[str] = None

    # Categorization
    category: CategoryEnum = Field(index=True)
    confidence_score: float = Field(ge=0.0, le=1.0)

    # Recurring Detection
    is_recurring: bool = Field(default=False)

    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user: Optional["User"] = Relationship(back_populates="transactions")
```

**Step 2: Add `transactions` relationship to `app/models/user.py`**

Find the existing `conversations` relationship and add the `transactions` relationship below it:

```python
# In the User class, add:
from typing import List  # already imported
transactions: List["Transaction"] = Relationship(back_populates="user")
```

Add the import at the top if not already there:
```python
from app.models.transaction import Transaction  # use TYPE_CHECKING if circular
```

Use `TYPE_CHECKING` guard if needed to avoid circular imports (same pattern as `Conversation`).

**Step 3: Update `app/models/__init__.py`**

Add exports:
```python
from app.models.transaction import CategoryEnum, Transaction
```

**Step 4: Verify no import errors**

```bash
cd /path/to/server && python -c "from app.models.transaction import Transaction, CategoryEnum; print('OK')"
```

Expected: `OK`

**Step 5: Commit**

```bash
git add app/models/transaction.py app/models/user.py app/models/__init__.py
git commit -m "feat: add Transaction model and CategoryEnum"
```

---

## Task 2: Schemas and TransactionFilters

**Files:**
- Create: `app/schemas/transaction.py`
- Modify: `app/schemas/__init__.py` (export new schemas)

**Step 1: Create `app/schemas/transaction.py`**

```python
from datetime import datetime
from typing import Annotated, Literal, Optional

from fastapi import Query
from sqlmodel import Field, SQLModel

from app.models.transaction import CategoryEnum


# ── Request Schemas ───────────────────────────────────────────────────────────

class TransactionCreate(SQLModel):
    """Request body for creating a single transaction.

    confidence_score defaults to 1.0 (human-verified) for manual entries.
    """

    date: datetime
    merchant: str = Field(min_length=1, max_length=255)
    amount: float
    category: CategoryEnum
    description: Optional[str] = Field(default=None, max_length=1000)
    original_category: Optional[str] = Field(default=None, max_length=255)
    is_recurring: bool = False
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class TransactionUpdate(SQLModel):
    """Request body for partially updating a single transaction."""

    date: Optional[datetime] = None
    merchant: Optional[str] = Field(default=None, min_length=1, max_length=255)
    amount: Optional[float] = None
    description: Optional[str] = Field(default=None, max_length=1000)
    original_category: Optional[str] = Field(default=None, max_length=255)
    category: Optional[CategoryEnum] = None
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    is_recurring: Optional[bool] = None


class BatchUpdateItem(SQLModel):
    """A single item in a batch update request."""

    id: int
    date: Optional[datetime] = None
    merchant: Optional[str] = Field(default=None, min_length=1, max_length=255)
    amount: Optional[float] = None
    description: Optional[str] = Field(default=None, max_length=1000)
    original_category: Optional[str] = Field(default=None, max_length=255)
    category: Optional[CategoryEnum] = None
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    is_recurring: Optional[bool] = None


class BatchUpdateRequest(SQLModel):
    """Request body for batch updating transactions. Max 100 items."""

    items: list[BatchUpdateItem] = Field(min_length=1, max_length=100)


class BatchDeleteRequest(SQLModel):
    """Request body for batch deleting transactions. Max 100 items."""

    ids: list[int] = Field(min_length=1, max_length=100)


# ── Response Schemas ──────────────────────────────────────────────────────────

class TransactionResponse(SQLModel):
    """Response schema for a single transaction."""

    id: int
    user_id: str
    date: datetime
    merchant: str
    amount: float
    description: Optional[str]
    original_category: Optional[str]
    category: CategoryEnum
    confidence_score: float
    is_recurring: bool
    created_at: datetime
    updated_at: datetime


class TransactionListResponse(SQLModel):
    """Paginated list of transactions."""

    items: list[TransactionResponse]
    total: int
    offset: int
    limit: int


class BatchUpdateResponse(SQLModel):
    """Response for a batch update operation."""

    updated: int


class BatchDeleteResponse(SQLModel):
    """Response for a batch delete operation."""

    deleted: int


# ── Filter Dependency ─────────────────────────────────────────────────────────

class TransactionFilters:
    """FastAPI dependency for transaction list query parameters."""

    def __init__(
        self,
        date_from: Optional[datetime] = Query(None, description="Filter transactions on or after this date"),
        date_to: Optional[datetime] = Query(None, description="Filter transactions on or before this date"),
        category: Optional[CategoryEnum] = Query(None, description="Filter by category"),
        merchant: Optional[str] = Query(None, description="Substring match on merchant name"),
        amount_min: Optional[float] = Query(None, description="Minimum transaction amount"),
        amount_max: Optional[float] = Query(None, description="Maximum transaction amount"),
        is_recurring: Optional[bool] = Query(None, description="Filter by recurring status"),
        sort_by: Literal["date", "amount", "merchant"] = Query("date", description="Field to sort by"),
        sort_order: Literal["asc", "desc"] = Query("desc", description="Sort direction"),
    ) -> None:
        self.date_from = date_from
        self.date_to = date_to
        self.category = category
        self.merchant = merchant
        self.amount_min = amount_min
        self.amount_max = amount_max
        self.is_recurring = is_recurring
        self.sort_by = sort_by
        self.sort_order = sort_order
```

**Step 2: Update `app/schemas/__init__.py`**

Add exports for all new schemas.

**Step 3: Verify no import errors**

```bash
python -c "from app.schemas.transaction import TransactionCreate, TransactionFilters; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add app/schemas/transaction.py app/schemas/__init__.py
git commit -m "feat: add transaction schemas and TransactionFilters"
```

---

## Task 3: Domain exceptions

**Files:**
- Create: `app/services/transaction/__init__.py`
- Create: `app/services/transaction/exceptions.py`

**Step 1: Create `app/services/transaction/exceptions.py`**

```python
from app.exceptions.base import NotFoundError


class TransactionNotFoundError(NotFoundError):
    """Raised when a transaction is not found or does not belong to the requesting user."""

    error_code = "TRANSACTION_NOT_FOUND"
```

**Step 2: Create `app/services/transaction/__init__.py`**

```python
from app.services.transaction.exceptions import TransactionNotFoundError

__all__ = ["TransactionNotFoundError"]
```

**Step 3: Verify**

```bash
python -c "from app.services.transaction.exceptions import TransactionNotFoundError; print('OK')"
```

**Step 4: Commit**

```bash
git add app/services/transaction/
git commit -m "feat: add transaction domain exceptions"
```

---

## Task 4: Unit tests (write before service — they will fail)

**Files:**
- Create: `tests/unit/services/__init__.py`
- Create: `tests/unit/services/test_transaction_service.py`

**Step 1: Create `tests/unit/services/test_transaction_service.py`**

```python
"""Unit tests for TransactionService.

All DB interactions are mocked — no real database required.
"""

from datetime import datetime
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
        original_time = datetime(2024, 1, 1)
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
```

**Step 2: Run tests — verify they FAIL**

```bash
pytest tests/unit/services/test_transaction_service.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` for `TransactionService` — this confirms the tests are real.

**Step 3: Commit the failing tests**

```bash
git add tests/unit/services/
git commit -m "test: add failing unit tests for TransactionService"
```

---

## Task 5: TransactionService (make unit tests pass)

**Files:**
- Create: `app/services/transaction/service.py`
- Modify: `app/services/transaction/__init__.py` (export singleton)

**Step 1: Create `app/services/transaction/service.py`**

```python
"""Transaction service — all business logic for transaction CRUD."""

from datetime import datetime

from sqlalchemy import func
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.schemas.transaction import (
    BatchUpdateItem,
    TransactionCreate,
    TransactionFilters,
    TransactionUpdate,
)
from app.services.transaction.exceptions import TransactionNotFoundError
from app.core.logging import get_logger

logger = get_logger(__name__)


class TransactionService:
    """Stateless service for transaction CRUD operations."""

    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: str,
        data: TransactionCreate,
    ) -> Transaction:
        """Create a new transaction.

        Args:
            db: Database session.
            user_id: Internal user ID sourced from auth — never from request body.
            data: Validated transaction data. confidence_score defaults to 1.0.

        Returns:
            The created Transaction.
        """
        transaction = Transaction(
            user_id=user_id,
            **data.model_dump(),
        )
        db.add(transaction)
        await db.flush()
        await db.refresh(transaction)

        logger.info("transaction_created", user_id=user_id, transaction_id=transaction.id)
        return transaction

    @staticmethod
    async def get(
        db: AsyncSession,
        user_id: str,
        transaction_id: int,
    ) -> Transaction:
        """Fetch a single transaction by ID, scoped to the requesting user.

        Raises:
            TransactionNotFoundError: If not found or owned by another user.
        """
        stmt = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        transaction = result.scalar_one_or_none()

        if not transaction:
            raise TransactionNotFoundError(
                f"Transaction {transaction_id} not found",
                transaction_id=transaction_id,
            )

        return transaction

    @staticmethod
    async def list(
        db: AsyncSession,
        user_id: str,
        filters: TransactionFilters,
        offset: int,
        limit: int,
    ) -> tuple[list[Transaction], int]:
        """List transactions with filters and pagination.

        Returns:
            Tuple of (transactions, total_count).
        """
        conditions = [
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        ]

        if filters.date_from:
            conditions.append(Transaction.date >= filters.date_from)
        if filters.date_to:
            conditions.append(Transaction.date <= filters.date_to)
        if filters.category:
            conditions.append(Transaction.category == filters.category)
        if filters.merchant:
            conditions.append(Transaction.merchant.ilike(f"%{filters.merchant}%"))
        if filters.amount_min is not None:
            conditions.append(Transaction.amount >= filters.amount_min)
        if filters.amount_max is not None:
            conditions.append(Transaction.amount <= filters.amount_max)
        if filters.is_recurring is not None:
            conditions.append(Transaction.is_recurring == filters.is_recurring)

        count_stmt = select(func.count()).select_from(Transaction).where(*conditions)
        total = await db.scalar(count_stmt) or 0

        sort_col = getattr(Transaction, filters.sort_by)
        ordered = sort_col.desc() if filters.sort_order == "desc" else sort_col.asc()

        data_stmt = (
            select(Transaction)
            .where(*conditions)
            .order_by(ordered)
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(data_stmt)
        return list(result.scalars().all()), total

    @staticmethod
    async def update(
        db: AsyncSession,
        user_id: str,
        transaction_id: int,
        data: TransactionUpdate,
    ) -> Transaction:
        """Partially update a transaction.

        Raises:
            TransactionNotFoundError: If not found or owned by another user.
        """
        stmt = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        transaction = result.scalar_one_or_none()

        if not transaction:
            raise TransactionNotFoundError(
                f"Transaction {transaction_id} not found",
                transaction_id=transaction_id,
            )

        update_data = data.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(transaction, field, value)
        transaction.updated_at = datetime.utcnow()

        db.add(transaction)
        await db.flush()
        await db.refresh(transaction)

        logger.info("transaction_updated", user_id=user_id, transaction_id=transaction_id)
        return transaction

    @staticmethod
    async def delete(
        db: AsyncSession,
        user_id: str,
        transaction_id: int,
    ) -> None:
        """Soft-delete a transaction (sets deleted_at).

        Raises:
            TransactionNotFoundError: If not found or owned by another user.
        """
        stmt = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        transaction = result.scalar_one_or_none()

        if not transaction:
            raise TransactionNotFoundError(
                f"Transaction {transaction_id} not found",
                transaction_id=transaction_id,
            )

        transaction.soft_delete()
        transaction.updated_at = datetime.utcnow()
        db.add(transaction)
        await db.flush()

        logger.info("transaction_deleted", user_id=user_id, transaction_id=transaction_id)

    @staticmethod
    async def batch_update(
        db: AsyncSession,
        user_id: str,
        items: list[BatchUpdateItem],
    ) -> int:
        """Update multiple transactions atomically.

        All-or-nothing: raises TransactionNotFoundError if any ID is invalid,
        which causes the caller's session to roll back all changes.

        Returns:
            Count of updated transactions.
        """
        for item in items:
            stmt = select(Transaction).where(
                Transaction.id == item.id,
                Transaction.user_id == user_id,
                Transaction.deleted_at.is_(None),
            )
            result = await db.execute(stmt)
            transaction = result.scalar_one_or_none()

            if not transaction:
                raise TransactionNotFoundError(
                    f"Transaction {item.id} not found",
                    transaction_id=item.id,
                )

            update_data = item.model_dump(exclude={"id"}, exclude_none=True)
            for field, value in update_data.items():
                setattr(transaction, field, value)
            transaction.updated_at = datetime.utcnow()
            db.add(transaction)

        await db.flush()
        logger.info("transactions_batch_updated", user_id=user_id, count=len(items))
        return len(items)

    @staticmethod
    async def batch_delete(
        db: AsyncSession,
        user_id: str,
        ids: list[int],
    ) -> int:
        """Soft-delete multiple transactions atomically.

        All-or-nothing: raises TransactionNotFoundError if any ID is invalid,
        which causes the caller's session to roll back all changes.

        Returns:
            Count of soft-deleted transactions.
        """
        for transaction_id in ids:
            stmt = select(Transaction).where(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id,
                Transaction.deleted_at.is_(None),
            )
            result = await db.execute(stmt)
            transaction = result.scalar_one_or_none()

            if not transaction:
                raise TransactionNotFoundError(
                    f"Transaction {transaction_id} not found",
                    transaction_id=transaction_id,
                )

            transaction.soft_delete()
            transaction.updated_at = datetime.utcnow()
            db.add(transaction)

        await db.flush()
        logger.info("transactions_batch_deleted", user_id=user_id, count=len(ids))
        return len(ids)


transaction_service = TransactionService()
```

**Step 2: Update `app/services/transaction/__init__.py`**

```python
from app.services.transaction.exceptions import TransactionNotFoundError
from app.services.transaction.service import TransactionService, transaction_service

__all__ = ["TransactionNotFoundError", "TransactionService", "transaction_service"]
```

**Step 3: Run unit tests — verify they PASS**

```bash
pytest tests/unit/services/test_transaction_service.py -v
```

Expected: all tests `PASSED`.

**Step 4: Commit**

```bash
git add app/services/transaction/service.py app/services/transaction/__init__.py
git commit -m "feat: implement TransactionService"
```

---

## Task 6: Transaction router

**Files:**
- Create: `app/api/v1/transactions.py`

**Step 1: Create `app/api/v1/transactions.py`**

> Note: `/batch` routes MUST be registered before `/{transaction_id}` to avoid FastAPI treating "batch" as an ID.

```python
"""Transaction CRUD endpoints."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.database import DbSession
from app.core.config import settings
from app.core.limiter import limiter
from app.schemas.transaction import (
    BatchDeleteRequest,
    BatchDeleteResponse,
    BatchUpdateRequest,
    BatchUpdateResponse,
    TransactionCreate,
    TransactionFilters,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdate,
)
from app.services.transaction.service import transaction_service

router = APIRouter()


# ── Batch routes first (must precede /{transaction_id}) ───────────────────────

@router.patch(
    "/batch",
    response_model=BatchUpdateResponse,
    summary="Batch update transactions",
    description="Update multiple transactions in a single atomic operation. "
                "All-or-nothing: if any ID is not found the entire batch is rolled back.",
)
@limiter.limit("30/minute")
async def batch_update_transactions(
    request: Request,
    body: BatchUpdateRequest,
    db: DbSession,
    user: CurrentUser,
) -> BatchUpdateResponse:
    """Batch update transactions for the authenticated user.

    Args:
        request: FastAPI request (required for rate limiting).
        body: List of items to update, max 100.
        db: Database session.
        user: Authenticated user.

    Returns:
        Count of updated transactions.
    """
    count = await transaction_service.batch_update(db, user.id, body.items)
    return BatchUpdateResponse(updated=count)


@router.delete(
    "/batch",
    response_model=BatchDeleteResponse,
    summary="Batch delete transactions",
    description="Soft-delete multiple transactions in a single atomic operation. "
                "All-or-nothing: if any ID is not found the entire batch is rolled back.",
)
@limiter.limit("30/minute")
async def batch_delete_transactions(
    request: Request,
    body: BatchDeleteRequest,
    db: DbSession,
    user: CurrentUser,
) -> BatchDeleteResponse:
    """Batch soft-delete transactions for the authenticated user.

    Args:
        request: FastAPI request (required for rate limiting).
        body: List of transaction IDs to delete, max 100.
        db: Database session.
        user: Authenticated user.

    Returns:
        Count of deleted transactions.
    """
    count = await transaction_service.batch_delete(db, user.id, body.ids)
    return BatchDeleteResponse(deleted=count)


# ── Collection routes ─────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=TransactionResponse,
    status_code=201,
    summary="Create a transaction",
    description="Create a single transaction. confidence_score defaults to 1.0 for manual entries.",
)
@limiter.limit("60/minute")
async def create_transaction(
    request: Request,
    body: TransactionCreate,
    db: DbSession,
    user: CurrentUser,
) -> TransactionResponse:
    """Create a new transaction for the authenticated user.

    Args:
        request: FastAPI request (required for rate limiting).
        body: Transaction data. user_id is always sourced from auth.
        db: Database session.
        user: Authenticated user.

    Returns:
        The created transaction.
    """
    transaction = await transaction_service.create(db, user.id, body)
    return TransactionResponse.model_validate(transaction)


@router.get(
    "",
    response_model=TransactionListResponse,
    summary="List transactions",
    description="Get a paginated, filtered list of transactions. "
                "Supports both classic pagination and infinite scroll via offset/limit.",
)
@limiter.limit("120/minute")
async def list_transactions(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    filters: TransactionFilters = Depends(),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
) -> TransactionListResponse:
    """List transactions for the authenticated user.

    Args:
        request: FastAPI request (required for rate limiting).
        db: Database session.
        user: Authenticated user.
        filters: Query parameter filters (date range, category, merchant, etc.).
        offset: Pagination offset.
        limit: Page size (max 100).

    Returns:
        Paginated list of transactions with total count.
    """
    transactions, total = await transaction_service.list(db, user.id, filters, offset, limit)
    return TransactionListResponse(
        items=[TransactionResponse.model_validate(t) for t in transactions],
        total=total,
        offset=offset,
        limit=limit,
    )


# ── Item routes ───────────────────────────────────────────────────────────────

@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Get a transaction",
    description="Fetch a single transaction by ID. Returns 404 if not found or owned by another user.",
)
@limiter.limit("120/minute")
async def get_transaction(
    request: Request,
    transaction_id: int,
    db: DbSession,
    user: CurrentUser,
) -> TransactionResponse:
    """Get a single transaction by ID for the authenticated user.

    Args:
        request: FastAPI request (required for rate limiting).
        transaction_id: The transaction ID to fetch.
        db: Database session.
        user: Authenticated user.

    Returns:
        The transaction.
    """
    transaction = await transaction_service.get(db, user.id, transaction_id)
    return TransactionResponse.model_validate(transaction)


@router.patch(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Update a transaction",
    description="Partially update a transaction. Only provided fields are updated.",
)
@limiter.limit("60/minute")
async def update_transaction(
    request: Request,
    transaction_id: int,
    body: TransactionUpdate,
    db: DbSession,
    user: CurrentUser,
) -> TransactionResponse:
    """Partially update a transaction for the authenticated user.

    Args:
        request: FastAPI request (required for rate limiting).
        transaction_id: The transaction ID to update.
        body: Fields to update (all optional).
        db: Database session.
        user: Authenticated user.

    Returns:
        The updated transaction.
    """
    transaction = await transaction_service.update(db, user.id, transaction_id, body)
    return TransactionResponse.model_validate(transaction)


@router.delete(
    "/{transaction_id}",
    status_code=204,
    summary="Delete a transaction",
    description="Soft-delete a transaction (sets deleted_at). The record is excluded from all future queries.",
)
@limiter.limit("60/minute")
async def delete_transaction(
    request: Request,
    transaction_id: int,
    db: DbSession,
    user: CurrentUser,
) -> None:
    """Soft-delete a transaction for the authenticated user.

    Args:
        request: FastAPI request (required for rate limiting).
        transaction_id: The transaction ID to delete.
        db: Database session.
        user: Authenticated user.
    """
    await transaction_service.delete(db, user.id, transaction_id)
```

**Step 2: Verify no import errors**

```bash
python -c "from app.api.v1.transactions import router; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add app/api/v1/transactions.py
git commit -m "feat: add transaction router with CRUD + batch endpoints"
```

---

## Task 7: Register router

**Files:**
- Modify: `app/api/v1/api.py`

**Step 1: Add the transactions router**

In `app/api/v1/api.py`, add:

```python
from app.api.v1.transactions import router as transactions_router

# With the other include_router calls:
api_router.include_router(transactions_router, prefix="/transactions", tags=["transactions"])
```

**Step 2: Start the app and verify the routes appear**

```bash
python -c "
from app.main import app
routes = [r.path for r in app.routes]
tx_routes = [r for r in routes if 'transaction' in r]
print('\n'.join(tx_routes))
"
```

Expected output (7 routes):
```
/api/v1/transactions/batch
/api/v1/transactions/batch
/api/v1/transactions
/api/v1/transactions
/api/v1/transactions/{transaction_id}
/api/v1/transactions/{transaction_id}
/api/v1/transactions/{transaction_id}
```

**Step 3: Commit**

```bash
git add app/api/v1/api.py
git commit -m "feat: register transactions router at /api/v1/transactions"
```

---

## Task 8: Integration tests

**Files:**
- Create: `tests/integration/test_transactions_api.py`

**Step 1: Check `tests/conftest.py`** for existing fixtures:
- `db_session` — async DB session for test DB
- `client` — `AsyncClient` with `ASGITransport`
- Any existing auth mock fixtures

**Step 2: Create `tests/integration/test_transactions_api.py`**

```python
"""Integration tests for /api/v1/transactions endpoints.

Uses a real test database and mocked auth (clerk_id injected via dependency override).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlmodel import select

from app.api.dependencies.auth import get_current_user
from app.models.transaction import CategoryEnum, Transaction
from app.models.user import User

pytestmark = pytest.mark.integration

MOCK_CLERK_ID = "clerk_test_user_001"
BASE_URL = "/api/v1/transactions"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_user(db_session):
    """Create a test user in the DB."""
    user = User(
        clerk_id=MOCK_CLERK_ID,
        email="test@example.com",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_client(client, test_user):
    """Client with auth dependency overridden to return test_user."""
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def transaction(db_session, test_user):
    """A single transaction belonging to test_user."""
    tx = Transaction(
        user_id=test_user.id,
        date=datetime(2024, 3, 15, tzinfo=timezone.utc),
        merchant="Supermarket ABC",
        amount=42.50,
        category=CategoryEnum.FOOD_GROCERIES,
        confidence_score=1.0,
    )
    db_session.add(tx)
    await db_session.flush()
    await db_session.refresh(tx)
    return tx


@pytest_asyncio.fixture
async def other_user_transaction(db_session):
    """A transaction belonging to a different user."""
    other_user = User(clerk_id="clerk_other", email="other@example.com")
    db_session.add(other_user)
    await db_session.flush()
    await db_session.refresh(other_user)

    tx = Transaction(
        user_id=other_user.id,
        date=datetime(2024, 3, 15, tzinfo=timezone.utc),
        merchant="Other Bank",
        amount=100.0,
        category=CategoryEnum.MISCELLANEOUS,
        confidence_score=1.0,
    )
    db_session.add(tx)
    await db_session.flush()
    await db_session.refresh(tx)
    return tx


# ── Auth tests ────────────────────────────────────────────────────────────────

class TestAuth:
    @pytest.mark.asyncio
    async def test_unauthenticated_get_returns_401(self, client):
        response = await client.get(BASE_URL)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unauthenticated_post_returns_401(self, client):
        response = await client.post(BASE_URL, json={})
        assert response.status_code == 401


# ── Create ────────────────────────────────────────────────────────────────────

class TestCreate:
    @pytest.mark.asyncio
    async def test_creates_transaction(self, auth_client, db_session, test_user):
        payload = {
            "date": "2024-03-15T10:00:00",
            "merchant": "Coffee Shop",
            "amount": 4.50,
            "category": "Bars & Restaurants",
        }
        response = await auth_client.post(BASE_URL, json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["merchant"] == "Coffee Shop"
        assert data["confidence_score"] == 1.0
        assert data["user_id"] == test_user.id

    @pytest.mark.asyncio
    async def test_validation_error_on_missing_required_field(self, auth_client):
        payload = {"merchant": "Shop", "amount": 10.0}  # missing date and category
        response = await auth_client.post(BASE_URL, json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_validation_error_on_invalid_confidence_score(self, auth_client):
        payload = {
            "date": "2024-03-15T10:00:00",
            "merchant": "Shop",
            "amount": 10.0,
            "category": "Shopping",
            "confidence_score": 1.5,  # > 1.0
        }
        response = await auth_client.post(BASE_URL, json=payload)
        assert response.status_code == 422


# ── List ──────────────────────────────────────────────────────────────────────

class TestList:
    @pytest.mark.asyncio
    async def test_returns_only_own_transactions(
        self, auth_client, transaction, other_user_transaction
    ):
        response = await auth_client.get(BASE_URL)

        assert response.status_code == 200
        data = response.json()
        ids = [item["id"] for item in data["items"]]
        assert transaction.id in ids
        assert other_user_transaction.id not in ids

    @pytest.mark.asyncio
    async def test_excludes_soft_deleted_transactions(
        self, auth_client, db_session, test_user, transaction
    ):
        transaction.soft_delete()
        db_session.add(transaction)
        await db_session.flush()

        response = await auth_client.get(BASE_URL)

        ids = [item["id"] for item in response.json()["items"]]
        assert transaction.id not in ids

    @pytest.mark.asyncio
    async def test_pagination_offset_and_limit(self, auth_client, db_session, test_user):
        # Create 5 transactions
        for i in range(5):
            db_session.add(Transaction(
                user_id=test_user.id,
                date=datetime(2024, 1, i + 1, tzinfo=timezone.utc),
                merchant=f"Merchant {i}",
                amount=float(i),
                category=CategoryEnum.MISCELLANEOUS,
                confidence_score=1.0,
            ))
        await db_session.flush()

        response = await auth_client.get(f"{BASE_URL}?offset=0&limit=2")
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 5
        assert data["offset"] == 0
        assert data["limit"] == 2

    @pytest.mark.asyncio
    async def test_filter_by_category(self, auth_client, db_session, test_user):
        db_session.add(Transaction(
            user_id=test_user.id,
            date=datetime(2024, 3, 1, tzinfo=timezone.utc),
            merchant="Gym",
            amount=30.0,
            category=CategoryEnum.LEISURE_ENTERTAINMENT,
            confidence_score=1.0,
        ))
        await db_session.flush()

        response = await auth_client.get(
            f"{BASE_URL}?category={CategoryEnum.LEISURE_ENTERTAINMENT.value}"
        )
        data = response.json()
        assert all(item["category"] == CategoryEnum.LEISURE_ENTERTAINMENT for item in data["items"])

    @pytest.mark.asyncio
    async def test_filter_by_merchant_substring(self, auth_client, transaction):
        response = await auth_client.get(f"{BASE_URL}?merchant=supermarket")
        data = response.json()
        assert any(item["id"] == transaction.id for item in data["items"])


# ── Get single ────────────────────────────────────────────────────────────────

class TestGetSingle:
    @pytest.mark.asyncio
    async def test_returns_own_transaction(self, auth_client, transaction):
        response = await auth_client.get(f"{BASE_URL}/{transaction.id}")
        assert response.status_code == 200
        assert response.json()["id"] == transaction.id

    @pytest.mark.asyncio
    async def test_returns_404_for_other_users_transaction(
        self, auth_client, other_user_transaction
    ):
        response = await auth_client.get(f"{BASE_URL}/{other_user_transaction.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_id(self, auth_client):
        response = await auth_client.get(f"{BASE_URL}/999999")
        assert response.status_code == 404


# ── Update ────────────────────────────────────────────────────────────────────

class TestUpdate:
    @pytest.mark.asyncio
    async def test_partial_update(self, auth_client, transaction):
        original_amount = transaction.amount
        response = await auth_client.patch(
            f"{BASE_URL}/{transaction.id}",
            json={"merchant": "Updated Merchant"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["merchant"] == "Updated Merchant"
        assert data["amount"] == original_amount  # unchanged

    @pytest.mark.asyncio
    async def test_updated_at_is_refreshed(self, auth_client, db_session, transaction):
        original_updated_at = transaction.updated_at
        response = await auth_client.patch(
            f"{BASE_URL}/{transaction.id}",
            json={"merchant": "Changed"},
        )
        assert response.status_code == 200
        # Re-fetch to verify DB state
        await db_session.refresh(transaction)
        assert transaction.updated_at >= original_updated_at

    @pytest.mark.asyncio
    async def test_returns_404_for_other_users_transaction(
        self, auth_client, other_user_transaction
    ):
        response = await auth_client.patch(
            f"{BASE_URL}/{other_user_transaction.id}",
            json={"merchant": "Hack"},
        )
        assert response.status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────

class TestDelete:
    @pytest.mark.asyncio
    async def test_soft_deletes_transaction(self, auth_client, db_session, transaction):
        response = await auth_client.delete(f"{BASE_URL}/{transaction.id}")
        assert response.status_code == 204

        await db_session.refresh(transaction)
        assert transaction.deleted_at is not None

    @pytest.mark.asyncio
    async def test_deleted_transaction_excluded_from_list(
        self, auth_client, transaction
    ):
        await auth_client.delete(f"{BASE_URL}/{transaction.id}")
        list_response = await auth_client.get(BASE_URL)
        ids = [item["id"] for item in list_response.json()["items"]]
        assert transaction.id not in ids

    @pytest.mark.asyncio
    async def test_returns_404_for_other_users_transaction(
        self, auth_client, other_user_transaction
    ):
        response = await auth_client.delete(f"{BASE_URL}/{other_user_transaction.id}")
        assert response.status_code == 404


# ── Batch Update ──────────────────────────────────────────────────────────────

class TestBatchUpdate:
    @pytest.mark.asyncio
    async def test_updates_multiple_transactions(
        self, auth_client, db_session, test_user, transaction
    ):
        tx2 = Transaction(
            user_id=test_user.id,
            date=datetime(2024, 3, 16, tzinfo=timezone.utc),
            merchant="Old Name",
            amount=20.0,
            category=CategoryEnum.SHOPPING,
            confidence_score=1.0,
        )
        db_session.add(tx2)
        await db_session.flush()
        await db_session.refresh(tx2)

        response = await auth_client.patch(
            f"{BASE_URL}/batch",
            json={"items": [
                {"id": transaction.id, "merchant": "New A"},
                {"id": tx2.id, "merchant": "New B"},
            ]},
        )
        assert response.status_code == 200
        assert response.json()["updated"] == 2

    @pytest.mark.asyncio
    async def test_rolls_back_on_invalid_id(
        self, auth_client, db_session, transaction
    ):
        original_merchant = transaction.merchant
        response = await auth_client.patch(
            f"{BASE_URL}/batch",
            json={"items": [
                {"id": transaction.id, "merchant": "Changed"},
                {"id": 999999, "merchant": "Bad"},
            ]},
        )
        assert response.status_code == 404
        await db_session.refresh(transaction)
        assert transaction.merchant == original_merchant  # rolled back

    @pytest.mark.asyncio
    async def test_validation_error_on_oversized_batch(self, auth_client):
        items = [{"id": i, "merchant": "x"} for i in range(101)]
        response = await auth_client.patch(
            f"{BASE_URL}/batch", json={"items": items}
        )
        assert response.status_code == 422


# ── Batch Delete ──────────────────────────────────────────────────────────────

class TestBatchDelete:
    @pytest.mark.asyncio
    async def test_soft_deletes_multiple_transactions(
        self, auth_client, db_session, test_user, transaction
    ):
        tx2 = Transaction(
            user_id=test_user.id,
            date=datetime(2024, 3, 17, tzinfo=timezone.utc),
            merchant="Another",
            amount=15.0,
            category=CategoryEnum.SHOPPING,
            confidence_score=1.0,
        )
        db_session.add(tx2)
        await db_session.flush()
        await db_session.refresh(tx2)

        response = await auth_client.delete(
            f"{BASE_URL}/batch",
            json={"ids": [transaction.id, tx2.id]},
        )
        assert response.status_code == 200
        assert response.json()["deleted"] == 2

        await db_session.refresh(transaction)
        await db_session.refresh(tx2)
        assert transaction.deleted_at is not None
        assert tx2.deleted_at is not None

    @pytest.mark.asyncio
    async def test_rolls_back_on_invalid_id(
        self, auth_client, db_session, transaction
    ):
        response = await auth_client.delete(
            f"{BASE_URL}/batch",
            json={"ids": [transaction.id, 999999]},
        )
        assert response.status_code == 404
        await db_session.refresh(transaction)
        assert transaction.deleted_at is None  # rolled back

    @pytest.mark.asyncio
    async def test_returns_404_for_other_users_transactions(
        self, auth_client, other_user_transaction
    ):
        response = await auth_client.delete(
            f"{BASE_URL}/batch",
            json={"ids": [other_user_transaction.id]},
        )
        assert response.status_code == 404
```

**Step 3: Run integration tests**

```bash
pytest tests/integration/test_transactions_api.py -v
```

Fix any failures before proceeding.

**Step 4: Commit**

```bash
git add tests/integration/test_transactions_api.py
git commit -m "test: add integration tests for transactions API"
```

---

## Task 9: Alembic migration

**Step 1: Generate the migration**

```bash
alembic revision --autogenerate -m "add_transaction_table"
```

Expected: new file created in `alembic/versions/`.

**Step 2: Review the generated migration**

Open the new file and verify:
- `transaction` table is created with all columns
- Indexes on `user_id`, `date`, `category` are present
- `downgrade()` drops the table and indexes

If the autogenerate missed indexes, add them manually:
```python
op.create_index("ix_transaction_user_id", "transaction", ["user_id"])
op.create_index("ix_transaction_date", "transaction", ["date"])
op.create_index("ix_transaction_category", "transaction", ["category"])
```

**Step 3: Apply the migration**

```bash
alembic upgrade head
```

Expected: `Running upgrade ... -> <revision_id>`

**Step 4: Commit**

```bash
git add alembic/versions/
git commit -m "feat: add migration for transaction table"
```

---

## Final verification

Run the full test suite:

```bash
pytest tests/unit/services/test_transaction_service.py tests/integration/test_transactions_api.py -v
```

All tests should pass. If the dev server is running, verify the OpenAPI docs at `/docs` show the 7 transaction endpoints.
