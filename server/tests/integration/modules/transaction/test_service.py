"""TransactionService against a real database."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.transaction import DuplicateTransactionError
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
