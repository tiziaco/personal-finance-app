"""Transaction service — all business logic for transaction CRUD."""

from datetime import UTC, datetime
from typing import List

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
            transaction.updated_at = datetime.now(UTC)
            db.add(transaction)

        await db.flush()
        logger.info("transactions_batch_updated", user_id=user_id, count=len(items))
        return len(items)

    @staticmethod
    async def batch_delete(
        db: AsyncSession,
        user_id: str,
        ids: List[int],
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
            transaction.updated_at = datetime.now(UTC)
            db.add(transaction)

        await db.flush()
        logger.info("transactions_batch_deleted", user_id=user_id, count=len(ids))
        return len(ids)


transaction_service = TransactionService()
