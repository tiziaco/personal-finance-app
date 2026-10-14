"""Transaction repository: every query, each one scoped by user_id."""

import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import delete, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import logger
from app.modules.transaction.models import Transaction
from app.modules.transaction.schemas import TransactionFilters, TransactionOrdering

_ORDER_COLUMNS = {
    "date": Transaction.date,
    "amount": Transaction.amount,
    "merchant": func.lower(Transaction.merchant),
}


def _escape_like(term: str) -> str:
    r"""Make %, _ and \ match themselves in an ILIKE pattern escaped with a backslash."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class TransactionRepository:
    """Repository for transaction database operations."""

    @staticmethod
    async def get_active_for_user(
        session: AsyncSession, user_id: uuid.UUID, transaction_id: uuid.UUID
    ) -> Optional[Transaction]:
        """One active transaction of this user's, or None (missing, deleted or another user's)."""
        statement = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        )
        return (await session.execute(statement)).scalar_one_or_none()

    @staticmethod
    async def find_active_by_fingerprint(
        session: AsyncSession, user_id: uuid.UUID, fingerprint: str
    ) -> Optional[Transaction]:
        """The oldest active transaction of this user's with this fingerprint, or None."""
        statement = (
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.fingerprint == fingerprint,
                Transaction.deleted_at.is_(None),
            )
            .order_by(Transaction.created_at)
            .limit(1)
        )
        return (await session.execute(statement)).scalar_one_or_none()

    @staticmethod
    async def add(session: AsyncSession, transaction: Transaction) -> Transaction:
        """Insert one transaction and flush."""
        session.add(transaction)
        await session.flush()
        await session.refresh(transaction)
        logger.info("transaction_created", transaction_id=transaction.id, user_id=transaction.user_id)
        return transaction

    @staticmethod
    async def add_many(session: AsyncSession, user_id: uuid.UUID, transactions: list[Transaction]) -> int:
        """Insert many transactions with one flush (batched into multi-row INSERTs by the driver)."""
        session.add_all(transactions)
        await session.flush()
        logger.info("transactions_imported", user_id=user_id, count=len(transactions))
        return len(transactions)

    @staticmethod
    async def update(session: AsyncSession, transaction: Transaction, values: dict[str, Any]) -> Transaction:
        """Write `values` onto a loaded transaction and flush."""
        for name, value in values.items():
            setattr(transaction, name, value)
        session.add(transaction)
        await session.flush()
        await session.refresh(transaction)
        logger.info("transaction_updated", transaction_id=transaction.id, fields=sorted(values))
        return transaction

    @staticmethod
    async def soft_delete(session: AsyncSession, transaction: Transaction) -> None:
        """Stamp deleted_at on a loaded transaction and flush."""
        transaction.soft_delete()
        session.add(transaction)
        await session.flush()
        logger.info("transaction_soft_deleted", transaction_id=transaction.id)

    @staticmethod
    async def list_active_for_user(
        session: AsyncSession,
        user_id: uuid.UUID,
        filters: TransactionFilters,
        ordering: TransactionOrdering,
        search: Optional[str],
        offset: int,
        limit: int,
    ) -> tuple[list[Transaction], int]:
        """One page of a user's active transactions and the filtered total.

        Every ordering ends in created_at DESC, id DESC so pages are stable.
        """
        conditions = [Transaction.user_id == user_id, Transaction.deleted_at.is_(None)]
        if filters.date_from is not None:
            conditions.append(Transaction.date >= filters.date_from)
        if filters.date_to is not None:
            conditions.append(Transaction.date <= filters.date_to)
        if filters.category:
            conditions.append(Transaction.category.in_([c.value for c in filters.category]))
        if filters.amount_min is not None:
            conditions.append(Transaction.amount >= filters.amount_min)
        if filters.amount_max is not None:
            conditions.append(Transaction.amount <= filters.amount_max)
        if filters.is_recurring is not None:
            conditions.append(Transaction.is_recurring == filters.is_recurring)
        if search:
            conditions.append(Transaction.merchant.ilike(f"%{_escape_like(search)}%", escape="\\"))

        total = (await session.execute(select(func.count()).select_from(Transaction).where(*conditions))).scalar_one()

        column = _ORDER_COLUMNS[ordering.lstrip("-")]
        primary = column.desc() if ordering.startswith("-") else column.asc()
        statement = (
            select(Transaction)
            .where(*conditions)
            .order_by(primary, Transaction.created_at.desc(), Transaction.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list((await session.execute(statement)).scalars().all())
        return items, total

    @staticmethod
    async def set_category_for_ids(
        session: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID], category: str, confidence: float
    ) -> list[uuid.UUID]:
        """Recategorise this user's active rows among `ids` in one UPDATE; return the ids changed."""
        statement = (
            update(Transaction)
            .where(Transaction.id.in_(ids), Transaction.user_id == user_id, Transaction.deleted_at.is_(None))
            .values(category=category, confidence=confidence, updated_at=datetime.now(UTC))
            .returning(Transaction.id)
        )
        changed = list((await session.execute(statement)).scalars().all())
        logger.info("transactions_recategorised", user_id=user_id, count=len(changed))
        return changed

    @staticmethod
    async def soft_delete_ids(session: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID]) -> list[uuid.UUID]:
        """Stamp deleted_at on this user's active rows among `ids` in one UPDATE; return the ids changed."""
        now = datetime.now(UTC)
        statement = (
            update(Transaction)
            .where(Transaction.id.in_(ids), Transaction.user_id == user_id, Transaction.deleted_at.is_(None))
            .values(deleted_at=now, updated_at=now)
            .returning(Transaction.id)
        )
        changed = list((await session.execute(statement)).scalars().all())
        logger.info("transactions_soft_deleted", user_id=user_id, count=len(changed))
        return changed

    @staticmethod
    async def delete_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> int:
        """Permanently remove every row this user owns, soft-deleted included; return the count."""
        result = await session.execute(delete(Transaction).where(Transaction.user_id == user_id))
        logger.info("all_user_transactions_deleted", user_id=user_id, count=result.rowcount)
        return result.rowcount


transaction_repository = TransactionRepository()
