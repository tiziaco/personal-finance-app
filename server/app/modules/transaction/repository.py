"""Transaction repository: every query, each one scoped by user_id."""

import uuid
from typing import Optional

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import logger
from app.modules.transaction.models import Transaction
from app.modules.transaction.schemas import TransactionFilters

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
    async def add_many(session: AsyncSession, transactions: list[Transaction]) -> int:
        """Insert many transactions with one flush (batched into multi-row INSERTs by the driver)."""
        session.add_all(transactions)
        await session.flush()
        return len(transactions)

    @staticmethod
    async def save(session: AsyncSession, transaction: Transaction) -> Transaction:
        """Flush changes made to a loaded transaction."""
        session.add(transaction)
        await session.flush()
        await session.refresh(transaction)
        return transaction

    @staticmethod
    async def list_active_for_user(
        session: AsyncSession,
        user_id: uuid.UUID,
        filters: TransactionFilters,
        ordering: str,
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


transaction_repository = TransactionRepository()
