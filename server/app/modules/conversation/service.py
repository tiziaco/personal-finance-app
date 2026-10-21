"""Conversation management service."""

import uuid
from typing import (
    List,
    Optional,
)

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chatbot import ChatbotAgent
from app.agents.chatbot.title import generate_title
from app.core.logging import logger
from app.database.dependencies import release_connection
from app.modules.conversation.domain.chat import first_exchange, history
from app.modules.conversation.exceptions import ConversationNotFoundError
from app.modules.conversation.models import Conversation
from app.modules.conversation.repository import conversation_repository


class ConversationService:
    """Service for chat conversation management operations."""

    @staticmethod
    async def create_conversation(session: AsyncSession, user_id: uuid.UUID, name: str = "") -> Conversation:
        """Create a new chat conversation."""
        return await conversation_repository.create(session, user_id, name)

    @staticmethod
    async def get_conversation(session: AsyncSession, conversation_id: uuid.UUID) -> Optional[Conversation]:
        """Get a conversation by ID, soft-deleted included."""
        return await conversation_repository.get_by_id(session, conversation_id)

    @staticmethod
    async def get_user_conversations(session: AsyncSession, user_id: uuid.UUID) -> List[Conversation]:
        """Get a user's active conversations, newest first."""
        return await conversation_repository.list_active_for_user(session, user_id)

    @staticmethod
    async def update_conversation_name(session: AsyncSession, conversation_id: uuid.UUID, name: str) -> Conversation:
        """Update a conversation's name.

        Raises ConversationNotFoundError if there is no such conversation.
        """
        conversation = await conversation_repository.get_by_id(session, conversation_id)
        if not conversation:
            raise ConversationNotFoundError(
                f"Conversation {conversation_id} not found", conversation_id=conversation_id
            )

        return await conversation_repository.update_name(session, conversation, name)

    @staticmethod
    async def soft_delete_conversation(session: AsyncSession, conversation_id: uuid.UUID) -> bool:
        """Soft-delete a conversation. False if there is no such conversation."""
        return await conversation_repository.soft_delete(session, conversation_id)

    @staticmethod
    async def soft_delete_all_user_conversations(session: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
        """Soft-delete every active conversation for a user and return their IDs."""
        return await conversation_repository.soft_delete_active_for_user(session, user_id)

    @staticmethod
    async def list_user_conversation_ids(session: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
        """Every conversation id a user owns, deleted or not."""
        return await conversation_repository.list_ids_for_user(session, user_id)

    @staticmethod
    async def blank_all_user_conversation_names(session: AsyncSession, user_id: uuid.UUID) -> int:
        """Clear the name of every conversation a user owns, deleted or not.

        Part of erasure: a name is free text and may hold PII. Returns the
        number of rows touched.
        """
        return await conversation_repository.blank_names_for_user(session, user_id)

    @staticmethod
    async def generate_title(session: AsyncSession, conversation: Conversation, agent: ChatbotAgent) -> Conversation:
        """Name an untitled conversation from its first exchange.

        A no-op for a named conversation, and for one with no title to give: no
        reply yet, a model that fails, or one that answers with nothing usable. A
        title is cosmetic, and the client asks again after the next completed reply.
        """
        if conversation.name:
            return conversation

        await release_connection(session)
        messages, stopped = await agent.state(conversation.id)
        exchange = first_exchange(history(messages, stopped, agent.tool_titles))
        if exchange is None:
            return conversation
        user_text, reply_text = exchange
        try:
            # The module-level `generate_title` (app.agents.chatbot.title), not this method.
            title = await generate_title(user_text, reply_text, conversation.id, conversation.user_id)
        except Exception:
            logger.exception("conversation_title_generation_failed", conversation_id=conversation.id)
            return conversation
        if title is None:
            return conversation

        # The model call takes seconds: a rename made meanwhile wins.
        return await conversation_repository.set_name_if_untitled(session, conversation, title)


conversation_service = ConversationService()
