"""TransactionService.activity: what insights reads to know if its set is stale."""

import pytest

from app.modules.transaction import TransactionActivity
from app.modules.transaction.schemas import TransactionUpdate
from app.modules.transaction.service import transaction_service

pytestmark = pytest.mark.integration


async def test_activity_with_no_rows(db_session, test_user):
    assert await transaction_service.activity(db_session, test_user.id) == TransactionActivity(False, None)


async def test_activity_sees_an_edit_and_a_soft_delete(db_session, test_user, other_user, make_transaction):
    txn = await make_transaction(test_user)
    await make_transaction(other_user)  # another user's rows never count
    first = await transaction_service.activity(db_session, test_user.id)
    assert first.has_active is True
    assert first.last_changed_at == txn.updated_at

    edited = await transaction_service.update(db_session, txn, TransactionUpdate(merchant="Edited"))
    second = await transaction_service.activity(db_session, test_user.id)
    assert second.last_changed_at == edited.updated_at
    assert second.last_changed_at > first.last_changed_at

    await transaction_service.soft_delete(db_session, edited)
    third = await transaction_service.activity(db_session, test_user.id)
    assert third.has_active is False
    assert third.last_changed_at == edited.updated_at
    assert third.last_changed_at >= second.last_changed_at
