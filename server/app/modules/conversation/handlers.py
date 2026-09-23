"""Subscriptions to account events."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.shared.checkpointing import delete_conversation_checkpoints
from app.core.events import events
from app.modules.account import USER_ERASING
from app.modules.conversation.service import conversation_service


@events.on(USER_ERASING, inline=True)
async def erase_on_user_erasing(session: AsyncSession, user_id: str) -> None:
    """Erase what a user's conversations hold: the rows are soft-deleted, the messages gone, the names blank.

    Inline, in the publishing transaction and before the user row is
    anonymised. Checkpoints are keyed by conversation id and hold the message
    text, so they go before the names — a test observes the name at the
    moment each checkpoint is deleted.
    """
    conversation_ids = await conversation_service.soft_delete_all_user_conversations(session, user_id)
    for conversation_id in conversation_ids:
        await delete_conversation_checkpoints(conversation_id)
    await conversation_service.blank_all_user_conversation_names(session, user_id)
