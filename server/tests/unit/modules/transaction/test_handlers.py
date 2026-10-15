"""The transaction module's reaction to USER_ERASING."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.events import events
from app.modules.account import USER_ERASING
from app.modules.transaction import handlers

pytestmark = pytest.mark.unit

USER_ID = uuid.UUID("0199a8b0-0000-7000-8000-000000000001")


def test_subscribes_inline_to_user_erasing():
    matches = [s for s in events.subscriptions(USER_ERASING) if s.handler is handlers.erase_on_user_erasing]
    assert matches, "erase_on_user_erasing is not subscribed to USER_ERASING"
    assert matches[0].inline


async def test_hard_deletes_every_transaction():
    session = AsyncMock()
    with patch(
        "app.modules.transaction.handlers.transaction_service.delete_all_for_user", new=AsyncMock(return_value=3)
    ) as delete_all:
        await handlers.erase_on_user_erasing(session=session, user_id=USER_ID)
    delete_all.assert_awaited_once_with(session, USER_ID)
