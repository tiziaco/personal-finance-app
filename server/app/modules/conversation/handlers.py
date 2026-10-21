"""Subscriptions to account events."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core import delete_conversations_checkpoints
from app.core.events import events
from app.modules.account import USER_ERASING
from app.modules.conversation.service import conversation_service


@events.on(USER_ERASING, inline=True)
async def erase_on_user_erasing(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Erase what a user's conversations hold: the rows are soft-deleted, the messages gone, the names blank.

    Inline, in the publishing transaction and before the user row is
    anonymised. Checkpoints are keyed by conversation id and hold the message
    text, so they go before the names — a test observes the name at the
    moment the checkpoints are deleted. They are cleared for every
    conversation the user owns, including ones deleted earlier: the delete
    route clears them as it goes, but erasure must not depend on that.
    """
    await conversation_service.soft_delete_all_user_conversations(session, user_id)
    conversation_ids = await conversation_service.list_user_conversation_ids(session, user_id)
    await delete_conversations_checkpoints(conversation_ids)
    await conversation_service.blank_all_user_conversation_names(session, user_id)
