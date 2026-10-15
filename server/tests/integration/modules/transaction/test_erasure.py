"""Erasure leaves the user no transaction rows, soft-deleted ones included."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import select

from app.modules.account import user_service
from app.modules.transaction.models import Transaction

pytestmark = pytest.mark.integration


async def test_erase_user_hard_deletes_their_transactions(
    db_session, test_user, other_user, make_transaction, stub_checkpoint_deletion
):
    await make_transaction(test_user)
    gone = await make_transaction(test_user, merchant="Deleted earlier")
    gone.soft_delete()
    kept = await make_transaction(other_user)

    with patch("app.modules.account.service.delete_user_memory", new=AsyncMock()):
        await user_service.erase_user(db_session, test_user)
    await db_session.flush()

    remaining = (await db_session.execute(select(Transaction))).scalars().all()
    assert [t.id for t in remaining] == [kept.id]
