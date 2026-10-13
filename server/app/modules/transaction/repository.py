"""Transaction repository: every query, each one scoped by user_id."""

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import logger
from app.modules.transaction.models import Transaction


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


transaction_repository = TransactionRepository()
