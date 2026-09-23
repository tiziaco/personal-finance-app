"""The conversation module's reaction to USER_ERASING."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.core.events import events
from app.modules.account import USER_ERASING
from app.modules.conversation import handlers

pytestmark = pytest.mark.unit


def test_subscribes_inline_to_user_erasing():
    matches = [s for s in events.subscriptions(USER_ERASING) if s.handler is handlers.erase_on_user_erasing]
    assert matches, "erase_on_user_erasing is not subscribed to USER_ERASING"
    assert matches[0].inline, "erase_on_user_erasing must be subscribed inline"


async def test_soft_deletes_clears_checkpoints_then_blanks_names_in_that_order():
    session = AsyncMock()
    session.add = MagicMock()
    parent = MagicMock()
    soft_delete = AsyncMock(return_value=["conv_1", "conv_2"])
    checkpoints = AsyncMock()
    blank = AsyncMock(return_value=2)
    parent.attach_mock(soft_delete, "soft_delete")
    parent.attach_mock(checkpoints, "checkpoints")
    parent.attach_mock(blank, "blank")

    with (
        patch(
            "app.modules.conversation.handlers.conversation_service.soft_delete_all_user_conversations",
            new=soft_delete,
        ),
        patch("app.modules.conversation.handlers.delete_conversation_checkpoints", new=checkpoints),
        patch("app.modules.conversation.handlers.conversation_service.blank_all_user_conversation_names", new=blank),
    ):
        await handlers.erase_on_user_erasing(session=session, user_id="u1")

    assert [c[0] for c in parent.mock_calls] == ["soft_delete", "checkpoints", "checkpoints", "blank"]
    assert checkpoints.await_args_list == [call("conv_1"), call("conv_2")]
    blank.assert_awaited_once_with(session, "u1")
