"""Transaction service."""

import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import events
from app.modules.transaction.domain import (
    DETECTED,
    USER,
    RecurringRow,
    detect_recurring,
    fingerprint,
    normalise_merchant,
    plan_count_matched,
)
from app.modules.transaction.exceptions import DuplicateTransactionError, TransactionNotFoundError
from app.modules.transaction.models import Transaction
from app.modules.transaction.repository import transaction_repository
from app.modules.transaction.schemas import (
    CATEGORIES,
    AnalysisRow,
    CategoryResponse,
    TransactionCreate,
    TransactionFilters,
    TransactionImport,
    TransactionOrdering,
    TransactionUpdate,
)

# Published for the modules above transaction (architecture §8). Only Settings'
# delete-all publishes it; erasure does not, its subscribers listen to USER_ERASING.
TRANSACTIONS_ALL_DELETED = "transaction.all_deleted"  # session, user_id — after the user's transactions are removed

# A category the user picked or confirmed by hand is certain (docs/data-model/transaction.md).
MANUAL_CONFIDENCE = 1.0


@dataclass(frozen=True)
class TransactionActivity:
    """Whether a user has any active rows, and when their data last moved."""

    has_active: bool
    last_changed_at: Optional[dt.datetime]


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
    async def _refresh_recurring(session: AsyncSession, user_id: uuid.UUID, keys: set[str]) -> None:
        """Re-judge every active row of these merchants; only `detected` rows change (docs/data-model/transaction.md, D6)."""
        if not keys:
            return
        rows = await transaction_repository.recurring_rows_for_keys(session, user_id, keys)
        current = {row.id: row.is_recurring for row in rows}
        by_key: dict[str, list[RecurringRow]] = {}
        for r in rows:
            by_key.setdefault(r.merchant_key, []).append(RecurringRow(r.id, r.date, r.amount, r.recurring_source))
        verdict: dict[uuid.UUID, bool] = {}
        for series in by_key.values():  # one merchant at a time: the rule judges a single key's rows
            verdict |= detect_recurring(series)
        now_true = [i for i, recurring in verdict.items() if recurring and not current[i]]
        now_false = [i for i, recurring in verdict.items() if not recurring and current[i]]
        await transaction_repository.set_recurring_for_ids(session, user_id, now_true, True)
        await transaction_repository.set_recurring_for_ids(session, user_id, now_false, False)

    @staticmethod
    async def create(session: AsyncSession, user_id: uuid.UUID, body: TransactionCreate) -> Transaction:
        """Add a transaction by hand. Raises DuplicateTransactionError on an active twin, unless allowed.

        A ticked Recurring box is the user's; an unticked one is left to the rule.
        """
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
            recurring_source=USER if body.is_recurring else DETECTED,
            fingerprint=key,
            merchant_key=normalise_merchant(body.merchant),
        )
        transaction = await transaction_repository.add(session, transaction)
        await TransactionService._refresh_recurring(session, user_id, {transaction.merchant_key})
        return await transaction_repository.refresh(session, transaction)

    @staticmethod
    async def update(session: AsyncSession, transaction: Transaction, body: TransactionUpdate) -> Transaction:
        """Apply a partial edit. An empty edit changes nothing; any edit sets confidence to 1.

        An edit that sends is_recurring makes it the user's. The rule re-runs for
        the merchant before and after the edit.
        """
        changes = body.model_dump(exclude_unset=True)
        if not changes:
            return transaction
        merged = {
            name: changes.get(name, getattr(transaction, name))
            for name in ("date", "merchant", "amount", "description")
        }
        old_key = transaction.merchant_key
        values = {
            **changes,
            "confidence": MANUAL_CONFIDENCE,
            "fingerprint": fingerprint(transaction.user_id, **merged),
            "merchant_key": normalise_merchant(merged["merchant"]),
        }
        if "is_recurring" in changes:
            values["recurring_source"] = USER
        updated = await transaction_repository.update(session, transaction, values)
        await TransactionService._refresh_recurring(session, updated.user_id, {old_key, updated.merchant_key})
        return await transaction_repository.refresh(session, updated)

    @staticmethod
    async def soft_delete(session: AsyncSession, transaction: Transaction) -> None:
        """Hide one transaction from every list; the row stays. Its merchant is re-judged."""
        await transaction_repository.soft_delete(session, transaction)
        await TransactionService._refresh_recurring(session, transaction.user_id, {transaction.merchant_key})

    @staticmethod
    async def which_are_new(
        session: AsyncSession, user_id: uuid.UUID, rows: list[tuple[dt.date, str, Decimal, Optional[str]]]
    ) -> list[bool]:
        """Which of a file's rows to import, each given as (date, merchant, amount, description).

        Count-matched (docs/data-model/transaction.md, D3): a row the user holds k
        times, among their active rows, keeps all but its first k copies.
        """
        prints = [fingerprint(user_id, *row) for row in rows]
        existing = await transaction_repository.count_active_by_fingerprints(session, user_id, prints)
        return plan_count_matched(prints, existing)

    @staticmethod
    async def import_many(session: AsyncSession, user_id: uuid.UUID, rows: list[TransactionImport]) -> int:
        """Insert rows that carry their own confidence and original category (the import; the seed).

        A ticked row is the user's, as in `create`; an unticked one is left to the rule, which re-runs for every merchant.
        """
        transactions = [
            Transaction(
                user_id=user_id,
                fingerprint=fingerprint(user_id, row.date, row.merchant, row.amount, row.description),
                merchant_key=normalise_merchant(row.merchant),
                recurring_source=USER if row.is_recurring else DETECTED,
                **row.model_dump(),
            )
            for row in rows
        ]
        count = await transaction_repository.add_many(session, user_id, transactions)
        await TransactionService._refresh_recurring(session, user_id, {t.merchant_key for t in transactions})
        return count

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
        """Soft-delete up to 100 transactions, all or none. Their merchants are re-judged."""
        keys = await transaction_repository.merchant_keys_for_ids(session, user_id, ids)
        changed = await transaction_repository.soft_delete_ids(session, user_id, ids)
        TransactionService._require_all(ids, changed)
        await TransactionService._refresh_recurring(session, user_id, keys)
        return len(changed)

    @staticmethod
    async def delete_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> int:
        """Permanently remove every transaction a user owns: Settings' delete-all and erasure."""
        return await transaction_repository.delete_all_for_user(session, user_id)

    @staticmethod
    async def delete_all_on_request(session: AsyncSession, user_id: uuid.UUID) -> int:
        """Settings' delete-all: remove every transaction, then tell the modules above.

        Erasure calls delete_all_for_user directly and does not publish; its subscribers
        listen to USER_ERASING.
        """
        count = await TransactionService.delete_all_for_user(session, user_id)
        await events.publish(TRANSACTIONS_ALL_DELETED, session=session, user_id=user_id)
        return count

    @staticmethod
    async def activity(session: AsyncSession, user_id: uuid.UUID) -> TransactionActivity:
        """Whether the user has active transactions, and the last change to any row, soft-deleted included."""
        has_active, last_changed_at = await transaction_repository.activity_for_user(session, user_id)
        return TransactionActivity(has_active, last_changed_at)

    @staticmethod
    async def list_for_analysis(
        session: AsyncSession,
        user_id: uuid.UUID,
        date_from: Optional[dt.date] = None,
        date_to: Optional[dt.date] = None,
    ) -> list[AnalysisRow]:
        """A user's active transactions in a range, as plain rows: analytics' only read."""
        return await transaction_repository.list_active_rows_for_analysis(session, user_id, date_from, date_to)

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
