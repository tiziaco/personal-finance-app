"""TransactionService against a real database."""

import datetime as dt
from decimal import Decimal

import pytest
from sqlmodel import select

from app.modules.transaction import DuplicateTransactionError, TransactionNotFoundError
from app.modules.transaction.models import Transaction
from app.modules.transaction.schemas import TransactionCreate, TransactionImport, TransactionUpdate
from app.modules.transaction.service import fingerprint, transaction_service

pytestmark = pytest.mark.integration


def _create(**overrides) -> TransactionCreate:
    return TransactionCreate(
        **(
            {
                "date": dt.date(2026, 3, 3),
                "merchant": "Späti",
                "amount": "-4.50",
                "category": "food_groceries",
            }
            | overrides
        )
    )


class TestCreate:
    async def test_sets_confidence_one_and_the_fingerprint(self, db_session, test_user):
        txn = await transaction_service.create(db_session, test_user.id, _create(description="Snack"))
        assert txn.confidence == 1.0
        assert txn.original_category is None
        assert txn.fingerprint == fingerprint(test_user.id, dt.date(2026, 3, 3), "Späti", Decimal("-4.50"), "Snack")

    async def test_a_duplicate_raises_with_the_existing_id(self, db_session, test_user, make_transaction):
        existing = await make_transaction(test_user)
        with pytest.raises(DuplicateTransactionError) as caught:
            await transaction_service.create(db_session, test_user.id, _create(merchant="  SPÄTI "))
        assert caught.value.context == {"existing_transaction_id": str(existing.id)}

    async def test_allow_duplicate_adds_it(self, db_session, test_user, make_transaction):
        existing = await make_transaction(test_user)
        txn = await transaction_service.create(db_session, test_user.id, _create(allow_duplicate=True))
        assert txn.id != existing.id
        assert txn.fingerprint == existing.fingerprint

    async def test_a_soft_deleted_twin_is_no_duplicate(self, db_session, test_user, make_transaction):
        twin = await make_transaction(test_user)
        await transaction_service.soft_delete(db_session, twin)
        txn = await transaction_service.create(db_session, test_user.id, _create())
        assert txn.id != twin.id

    async def test_another_users_twin_is_no_duplicate(self, db_session, test_user, other_user, make_transaction):
        await make_transaction(other_user)
        txn = await transaction_service.create(db_session, test_user.id, _create())
        assert txn.user_id == test_user.id


class TestUpdate:
    async def test_recomputes_the_fingerprint_and_sets_confidence_one(self, db_session, test_user, make_transaction):
        txn = await make_transaction(test_user, confidence=0.4)
        updated = await transaction_service.update(db_session, txn, TransactionUpdate(merchant="REWE"))
        assert updated.merchant == "REWE"
        assert updated.confidence == 1.0
        assert updated.fingerprint == fingerprint(test_user.id, txn.date, "REWE", txn.amount, None)

    async def test_category_only_edit_keeps_the_fingerprint(self, db_session, test_user, make_transaction):
        txn = await make_transaction(test_user)
        before = txn.fingerprint
        updated = await transaction_service.update(db_session, txn, TransactionUpdate(category="shopping"))
        assert updated.fingerprint == before

    async def test_null_description_clears_it(self, db_session, test_user, make_transaction):
        txn = await make_transaction(test_user, description="Old")
        updated = await transaction_service.update(
            db_session, txn, TransactionUpdate.model_validate({"description": None})
        )
        assert updated.description is None

    async def test_empty_patch_changes_nothing(self, db_session, test_user, make_transaction):
        """Review Focus 1: Save with no change sends {}."""
        txn = await make_transaction(test_user, confidence=0.4)
        updated_at = txn.updated_at
        updated = await transaction_service.update(db_session, txn, TransactionUpdate())
        assert updated.confidence == 0.4
        assert updated.updated_at == updated_at


class TestImportMany:
    async def test_keeps_confidence_and_original_category(self, db_session, test_user):
        rows = [
            TransactionImport(
                date=dt.date(2026, 3, 1),
                merchant="REWE",
                amount="-12.70",
                category="food_groceries",
                confidence=0.9,
                original_category="Presentment",
            ),
            TransactionImport(
                date=dt.date(2026, 3, 2),
                merchant="Employer GmbH",
                amount="2400.00",
                category="salary",
                confidence=1.0,
                is_recurring=True,
            ),
        ]
        assert await transaction_service.import_many(db_session, test_user.id, rows) == 2


class TestBatches:
    async def test_recategorise_sets_confidence_one(self, db_session, test_user, make_transaction):
        a = await make_transaction(test_user, confidence=0.3)
        b = await make_transaction(test_user, merchant="REWE", confidence=0.5)
        assert await transaction_service.batch_update_category(db_session, test_user.id, [a.id, b.id], "shopping") == 2
        await db_session.refresh(a)
        assert (a.category, a.confidence) == ("shopping", 1.0)

    async def test_one_foreign_id_raises(self, db_session, test_user, other_user, make_transaction):
        """The raise is what makes the session dependency roll the batch back (the route test proves it)."""
        mine = await make_transaction(test_user)
        theirs = await make_transaction(other_user)
        with pytest.raises(TransactionNotFoundError):
            await transaction_service.batch_update_category(db_session, test_user.id, [mine.id, theirs.id], "shopping")

    async def test_a_soft_deleted_id_counts_as_missing(self, db_session, test_user, make_transaction):
        a = await make_transaction(test_user)
        a.soft_delete()
        await db_session.flush()
        with pytest.raises(TransactionNotFoundError):
            await transaction_service.batch_soft_delete(db_session, test_user.id, [a.id])

    async def test_delete_all_removes_soft_deleted_rows_too(self, db_session, test_user, other_user, make_transaction):
        await make_transaction(test_user)
        hidden = await make_transaction(test_user, merchant="Hidden")
        hidden.soft_delete()
        await make_transaction(other_user)
        assert await transaction_service.delete_all_for_user(db_session, test_user.id) == 2


async def _series(db_session, user_id, key: str) -> list[tuple[bool, str]]:
    """(is_recurring, recurring_source) of a merchant key's active rows, oldest first, read fresh."""
    statement = (
        select(Transaction)
        .where(Transaction.user_id == user_id, Transaction.merchant_key == key, Transaction.deleted_at.is_(None))
        .order_by(Transaction.date)
        .execution_options(populate_existing=True)
    )
    return [(t.is_recurring, t.recurring_source) for t in (await db_session.execute(statement)).scalars()]


def _netflix(day: dt.date, **extra) -> TransactionCreate:
    return TransactionCreate(
        date=day, merchant="Netflix", amount=Decimal("-9.99"), category="leisure_entertainment", **extra
    )


class TestRecurringOnWrite:
    async def test_the_third_monthly_row_marks_the_series(self, db_session, test_user, make_transaction):
        await make_transaction(
            test_user, merchant="PAYPAL *NETFLIX 4029", amount=Decimal("-9.99"), date=dt.date(2026, 1, 5)
        )
        await make_transaction(test_user, merchant="NETFLIX.COM", amount=Decimal("-9.99"), date=dt.date(2026, 2, 5))

        created = await transaction_service.create(db_session, test_user.id, _netflix(dt.date(2026, 3, 5)))

        assert (created.is_recurring, created.recurring_source, created.merchant_key) == (True, "detected", "netflix")
        assert await _series(db_session, test_user.id, "netflix") == [(True, "detected")] * 3

    async def test_a_ticked_box_is_the_users_and_an_unticked_one_is_not(self, db_session, test_user):
        ticked = await transaction_service.create(
            db_session, test_user.id, _netflix(dt.date(2026, 1, 5), is_recurring=True)
        )
        unticked = await transaction_service.create(
            db_session,
            test_user.id,
            TransactionCreate(date=dt.date(2026, 1, 6), merchant="Kiosk", amount=Decimal("-2"), category="shopping"),
        )
        assert (ticked.is_recurring, ticked.recurring_source) == (True, "user")
        assert (unticked.is_recurring, unticked.recurring_source) == (False, "detected")

    async def test_a_users_edit_survives_the_rule(self, db_session, test_user, make_transaction):
        rows = [
            await make_transaction(test_user, merchant="Netflix", amount=Decimal("-9.99"), date=dt.date(2026, m, 5))
            for m in (1, 2, 3)
        ]
        await transaction_service.update(db_session, rows[0], TransactionUpdate(category="shopping"))  # runs the rule
        edited = await transaction_service.update(db_session, rows[1], TransactionUpdate(is_recurring=False))
        assert (edited.is_recurring, edited.recurring_source) == (False, "user")
        assert await _series(db_session, test_user.id, "netflix") == [
            (True, "detected"),
            (False, "user"),
            (True, "detected"),
        ]

    async def test_renaming_a_merchant_rejudges_both_keys(self, db_session, test_user, make_transaction):
        rows = [
            await make_transaction(
                test_user, merchant="Netflix", amount=Decimal("-9.99"), date=dt.date(2026, m, 5), is_recurring=True
            )
            for m in (1, 2, 3)
        ]
        renamed = await transaction_service.update(db_session, rows[2], TransactionUpdate(merchant="Spotify"))
        assert renamed.merchant_key == "spotify"
        assert await _series(db_session, test_user.id, "netflix") == [(False, "detected")] * 2

    async def test_deleting_one_breaks_the_series(self, db_session, test_user, make_transaction):
        rows = [
            await make_transaction(
                test_user, merchant="Netflix", amount=Decimal("-9.99"), date=dt.date(2026, m, 5), is_recurring=True
            )
            for m in (1, 2, 3)
        ]
        await transaction_service.soft_delete(db_session, rows[1])
        assert await _series(db_session, test_user.id, "netflix") == [(False, "detected")] * 2

    async def test_batch_delete_rejudges_the_keys(self, db_session, test_user, make_transaction):
        rows = [
            await make_transaction(
                test_user, merchant="Netflix", amount=Decimal("-9.99"), date=dt.date(2026, m, 5), is_recurring=True
            )
            for m in (1, 2, 3)
        ]
        await transaction_service.batch_soft_delete(db_session, test_user.id, [rows[0].id])
        assert await _series(db_session, test_user.id, "netflix") == [(False, "detected")] * 2

    async def test_import_many_runs_the_rule_and_honours_a_users_value(self, db_session, test_user):
        rows = [
            TransactionImport(
                date=dt.date(2026, m, 5),
                merchant="Netflix",
                amount=Decimal("-9.99"),
                category="leisure_entertainment",
                confidence=0.9,
            )
            for m in (1, 2, 3)
        ]
        pinned = TransactionImport(
            date=dt.date(2026, 3, 9),
            merchant="Kiosk",
            amount=Decimal("-2"),
            category="shopping",
            confidence=0.9,
            is_recurring=True,
        )
        assert await transaction_service.import_many(db_session, test_user.id, [*rows, pinned]) == 4
        assert await _series(db_session, test_user.id, "netflix") == [(True, "detected")] * 3
        assert await _series(db_session, test_user.id, "kiosk") == [(True, "user")]


class TestCountActiveByFingerprints:
    async def test_counts_active_rows_only(self, db_session, test_user, other_user, make_transaction):
        a = await make_transaction(test_user)
        await make_transaction(test_user)
        gone = await make_transaction(test_user, merchant="Gone")
        await transaction_service.soft_delete(db_session, gone)
        await make_transaction(other_user)

        counts = await transaction_service.count_active_by_fingerprints(
            db_session, test_user.id, [a.fingerprint, gone.fingerprint, "f" * 64]
        )
        assert counts == {a.fingerprint: 2}
