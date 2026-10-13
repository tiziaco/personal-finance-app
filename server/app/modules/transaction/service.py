"""Transaction service."""

import datetime as dt
import hashlib
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.modules.transaction.exceptions import DuplicateTransactionError
from app.modules.transaction.models import Transaction
from app.modules.transaction.repository import transaction_repository
from app.modules.transaction.schemas import (
    CATEGORIES,
    CategoryResponse,
    TransactionCreate,
    TransactionFilters,
    TransactionImport,
    TransactionUpdate,
)

_CENT = Decimal("0.01")


def fingerprint(user_id: uuid.UUID, date: dt.date, merchant: str, amount: Decimal, description: Optional[str]) -> str:
    """sha256 of user|date|merchant|amount|description — the duplicate key (docs/data-model/transaction.md).

    Merchant and description are stripped and casefolded; the amount is the
    Decimal at two places, never a float, and -0.00 is 0.00. Step 4's import
    uses the same function, so the two can never disagree.
    """
    cents = amount.quantize(_CENT)
    if cents == 0:
        cents = Decimal("0.00")
    raw = (
        f"{user_id}|{date:%Y-%m-%d}|{merchant.strip().casefold()}|{cents:.2f}|{(description or '').strip().casefold()}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class TransactionService:
    """Orchestrates transaction operations."""

    @staticmethod
    def list_categories() -> list[CategoryResponse]:
        """Every category, in display order."""
        return [CategoryResponse(value=slug, label=label) for slug, label in CATEGORIES]

    @staticmethod
    async def get_for_user(
        session: AsyncSession, user_id: uuid.UUID, transaction_id: uuid.UUID
    ) -> Optional[Transaction]:
        """One active transaction of this user's, or None."""
        return await transaction_repository.get_active_for_user(session, user_id, transaction_id)

    @staticmethod
    async def create(session: AsyncSession, user_id: uuid.UUID, body: TransactionCreate) -> Transaction:
        """Add a transaction by hand. Raises DuplicateTransactionError on an active twin, unless allowed."""
        key = fingerprint(user_id, body.date, body.merchant, body.amount, body.description)
        if not body.allow_duplicate:
            existing = await transaction_repository.find_active_by_fingerprint(session, user_id, key)
            if existing:
                # The id only: the caller already holds the fields that matched, and
                # merchant text would otherwise reach the error log.
                raise DuplicateTransactionError(
                    "A transaction with the same date, merchant, amount and description exists",
                    existing_transaction_id=str(existing.id),
                )
        transaction = Transaction(
            user_id=user_id,
            date=body.date,
            merchant=body.merchant,
            amount=body.amount,
            description=body.description,
            category=body.category,
            confidence=1.0,
            is_recurring=body.is_recurring,
            fingerprint=key,
        )
        return await transaction_repository.add(session, transaction)

    @staticmethod
    async def update(session: AsyncSession, transaction: Transaction, body: TransactionUpdate) -> Transaction:
        """Apply a partial edit. An empty edit changes nothing; any edit sets confidence to 1."""
        changes = {name: getattr(body, name) for name in body.model_fields_set}
        if not changes:
            return transaction
        for name, value in changes.items():
            setattr(transaction, name, value)
        transaction.confidence = 1.0
        transaction.fingerprint = fingerprint(
            transaction.user_id, transaction.date, transaction.merchant, transaction.amount, transaction.description
        )
        logger.info("transaction_updated", transaction_id=transaction.id, fields=sorted(changes))
        return await transaction_repository.save(session, transaction)

    @staticmethod
    async def soft_delete(session: AsyncSession, transaction: Transaction) -> None:
        """Hide one transaction from every list; the row stays."""
        transaction.soft_delete()
        await transaction_repository.save(session, transaction)
        logger.info("transaction_soft_deleted", transaction_id=transaction.id)

    @staticmethod
    async def import_many(session: AsyncSession, user_id: uuid.UUID, rows: list[TransactionImport]) -> int:
        """Insert rows that carry their own confidence and original category (the seed; step 4's import)."""
        transactions = [
            Transaction(
                user_id=user_id,
                fingerprint=fingerprint(user_id, row.date, row.merchant, row.amount, row.description),
                **row.model_dump(),
            )
            for row in rows
        ]
        count = await transaction_repository.add_many(session, transactions)
        logger.info("transactions_imported", user_id=user_id, count=count)
        return count

    @staticmethod
    async def list(
        session: AsyncSession,
        user_id: uuid.UUID,
        filters: TransactionFilters,
        ordering: str,
        search: Optional[str],
        offset: int,
        limit: int,
    ) -> tuple[list[Transaction], int]:
        """One page of a user's active transactions and the filtered total."""
        return await transaction_repository.list_active_for_user(
            session, user_id, filters, ordering, search, offset, limit
        )


transaction_service = TransactionService()
