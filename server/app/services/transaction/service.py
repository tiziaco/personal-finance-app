"""Transaction service — all business logic for transaction CRUD."""

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import List, Optional

import polars as pl
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import logger
from app.models.transaction import Transaction
from app.schemas.transaction import (
    BatchUpdateItem,
    TransactionCreate,
    TransactionFilters,
    TransactionUpdate,
)
from app.services.transaction.exceptions import TransactionNotFoundError


class TransactionService:
    """Stateless service for transaction CRUD operations."""

    @staticmethod
    def compute_fingerprint(
        user_id: str,
        date: datetime,
        merchant: str,
        amount: Decimal,
        description: Optional[str],
    ) -> str:
        """SHA-256 fingerprint for deduplication.

        Includes description because merchants like PayPal use it to
        distinguish recipients — same date/merchant/amount but different
        description = different transaction.
        """
        raw = (
            f"{user_id}|"
            f"{date.isoformat()}|"
            f"{merchant.strip().lower()}|"
            f"{float(amount):.2f}|"
            f"{(description or '').strip().lower()}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()

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
    ) -> tuple[List[Transaction], int]:
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
        return [*result.scalars().all()], total

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
        transaction.updated_at = datetime.now(UTC)

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
        transaction.updated_at = datetime.now(UTC)
        db.add(transaction)
        await db.flush()

        logger.info("transaction_deleted", user_id=user_id, transaction_id=transaction_id)

    @staticmethod
    async def batch_update(
        db: AsyncSession,
        user_id: str,
        items: List[BatchUpdateItem],
    ) -> int:
        """Update multiple transactions atomically.

        All-or-nothing: uses a savepoint so any failure rolls back all changes.

        Returns:
            Count of updated transactions.
        """
        async with db.begin_nested():
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
                transaction.updated_at = datetime.now(UTC)
                db.add(transaction)

        logger.info("transactions_batch_updated", user_id=user_id, count=len(items))
        return len(items)

    @staticmethod
    async def batch_delete(
        db: AsyncSession,
        user_id: str,
        ids: List[int],
    ) -> int:
        """Soft-delete multiple transactions atomically.

        All-or-nothing: uses a savepoint so any failure rolls back all changes.

        Returns:
            Count of soft-deleted transactions.
        """
        async with db.begin_nested():
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
                transaction.updated_at = datetime.now(UTC)
                db.add(transaction)

        logger.info("transactions_batch_deleted", user_id=user_id, count=len(ids))
        return len(ids)


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
            conditions.append(Transaction.date >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            conditions.append(Transaction.date <= datetime.combine(date_to, datetime.max.time()))

        stmt = select(Transaction).where(*conditions).order_by(Transaction.date)
        result = await db.execute(stmt)
        transactions = result.scalars().all()

        if not transactions:
            return pl.DataFrame(schema=empty_schema)

        rows = [
            {
                "date": t.date.date() if isinstance(t.date, datetime) else t.date,
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


transaction_service = TransactionService()
