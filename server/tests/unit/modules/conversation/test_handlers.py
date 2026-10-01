"""The conversation module's reaction to USER_ERASING."""

import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.core.events import events
from app.modules.account import USER_ERASING
from app.modules.conversation import handlers

pytestmark = pytest.mark.unit

USER_ID = uuid.UUID("0199a8b0-0000-7000-8000-000000000001")
CONV_0 = uuid.UUID("0199a8b0-0000-7000-8000-0000000000c0")
CONV_1 = uuid.UUID("0199a8b0-0000-7000-8000-0000000000c1")


def test_subscribes_inline_to_user_erasing():
    matches = [s for s in events.subscriptions(USER_ERASING) if s.handler is handlers.erase_on_user_erasing]
    assert matches, "erase_on_user_erasing is not subscribed to USER_ERASING"
    assert matches[0].inline, "erase_on_user_erasing must be subscribed inline"


async def test_soft_deletes_clears_checkpoints_then_blanks_names_in_that_order():
    session = AsyncMock()
    session.add = MagicMock()
    parent = MagicMock()
    soft_delete = AsyncMock(return_value=[CONV_1])
    list_ids = AsyncMock(return_value=[CONV_1, CONV_0])
    checkpoints = AsyncMock()
    blank = AsyncMock(return_value=2)
    parent.attach_mock(soft_delete, "soft_delete")
    parent.attach_mock(list_ids, "list_ids")
    parent.attach_mock(checkpoints, "checkpoints")
    parent.attach_mock(blank, "blank")

    with (
        patch(
            "app.modules.conversation.handlers.conversation_service.soft_delete_all_user_conversations",
            new=soft_delete,
        ),
        patch("app.modules.conversation.handlers.conversation_service.list_user_conversation_ids", new=list_ids),
        patch("app.modules.conversation.handlers.delete_conversations_checkpoints", new=checkpoints),
        patch("app.modules.conversation.handlers.conversation_service.blank_all_user_conversation_names", new=blank),
    ):
        await handlers.erase_on_user_erasing(session=session, user_id=USER_ID)

    assert [c[0] for c in parent.mock_calls] == ["soft_delete", "list_ids", "checkpoints", "blank"]
    # Every id the user owns, soft-deleted ones included — not only those just soft-deleted.
    checkpoints.assert_awaited_once_with([CONV_1, CONV_0])
    blank.assert_awaited_once_with(session, USER_ID)
