"""Transaction service."""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.transaction.domain import fingerprint
from app.modules.transaction.exceptions import DuplicateTransactionError, TransactionNotFoundError
from app.modules.transaction.models import Transaction
from app.modules.transaction.repository import transaction_repository
from app.modules.transaction.schemas import (
    CATEGORIES,
    CategoryResponse,
    TransactionCreate,
    TransactionFilters,
    TransactionImport,
    TransactionOrdering,
    TransactionUpdate,
)

# A category the user picked or confirmed by hand is certain (docs/data-model/transaction.md).
MANUAL_CONFIDENCE = 1.0


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
            confidence=MANUAL_CONFIDENCE,
            is_recurring=body.is_recurring,
            fingerprint=key,
        )
        return await transaction_repository.add(session, transaction)

    @staticmethod
    async def update(session: AsyncSession, transaction: Transaction, body: TransactionUpdate) -> Transaction:
        """Apply a partial edit. An empty edit changes nothing; any edit sets confidence to 1."""
        changes = body.model_dump(exclude_unset=True)
        if not changes:
            return transaction
        merged = {
            name: changes.get(name, getattr(transaction, name))
            for name in ("date", "merchant", "amount", "description")
        }
        key = fingerprint(transaction.user_id, **merged)
        return await transaction_repository.update(
            session, transaction, {**changes, "confidence": MANUAL_CONFIDENCE, "fingerprint": key}
        )

    @staticmethod
    async def soft_delete(session: AsyncSession, transaction: Transaction) -> None:
        """Hide one transaction from every list; the row stays."""
        await transaction_repository.soft_delete(session, transaction)

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
        return await transaction_repository.add_many(session, user_id, transactions)

    @staticmethod
    def _require_all(ids: list[uuid.UUID], changed: list[uuid.UUID]) -> None:
        """All or nothing: raising makes the session dependency roll the batch back."""
        if len(changed) != len(ids):
            missing = sorted(str(i) for i in set(ids) - set(changed))
            raise TransactionNotFoundError("One or more transactions not found", missing_ids=missing)

    @staticmethod
    async def batch_update_category(
        session: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID], category: str
    ) -> int:
        """Recategorise up to 100 transactions, all or none."""
        changed = await transaction_repository.set_category_for_ids(session, user_id, ids, category, MANUAL_CONFIDENCE)
        TransactionService._require_all(ids, changed)
        return len(changed)

    @staticmethod
    async def batch_soft_delete(session: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID]) -> int:
        """Soft-delete up to 100 transactions, all or none."""
        changed = await transaction_repository.soft_delete_ids(session, user_id, ids)
        TransactionService._require_all(ids, changed)
        return len(changed)

    @staticmethod
    async def delete_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> int:
        """Permanently remove every transaction a user owns: Settings' delete-all and erasure."""
        return await transaction_repository.delete_all_for_user(session, user_id)

    @staticmethod
    async def list(
        session: AsyncSession,
        user_id: uuid.UUID,
        filters: TransactionFilters,
        ordering: TransactionOrdering,
        search: Optional[str],
        offset: int,
        limit: int,
    ) -> tuple[list[Transaction], int]:
        """One page of a user's active transactions and the filtered total."""
        return await transaction_repository.list_active_for_user(
            session, user_id, filters, ordering, search, offset, limit
        )


transaction_service = TransactionService()
