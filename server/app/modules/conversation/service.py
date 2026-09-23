"""Conversation management service."""

from typing import (
    List,
    Optional,
)

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.conversation.exceptions import ConversationNotFoundError
from app.modules.conversation.models import Conversation
from app.modules.conversation.repository import conversation_repository


class ConversationService:
    """Service for chat conversation management operations."""

    @staticmethod
    async def create_conversation(
        session: AsyncSession, conversation_id: str, user_id: str, name: str = ""
    ) -> Conversation:
        """Create a new chat conversation."""
        return await conversation_repository.create(session, conversation_id, user_id, name)

    @staticmethod
    async def get_conversation(session: AsyncSession, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID, soft-deleted included."""
        return await conversation_repository.get_by_id(session, conversation_id)

    @staticmethod
    async def get_user_conversations(session: AsyncSession, user_id: str) -> List[Conversation]:
        """Get a user's active conversations, oldest first."""
        return await conversation_repository.list_active_for_user(session, user_id)

    @staticmethod
    async def update_conversation_name(session: AsyncSession, conversation_id: str, name: str) -> Conversation:
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
    async def soft_delete_conversation(session: AsyncSession, conversation_id: str) -> bool:
        """Soft-delete a conversation. False if there is no such conversation."""
        return await conversation_repository.soft_delete(session, conversation_id)

    @staticmethod
    async def soft_delete_all_user_conversations(session: AsyncSession, user_id: str) -> list[str]:
        """Soft-delete every active conversation for a user.

        Returns their IDs so the caller can clear each one's LangGraph
        checkpoint data.
        """
        return await conversation_repository.soft_delete_active_for_user(session, user_id)

    @staticmethod
    async def blank_all_user_conversation_names(session: AsyncSession, user_id: str) -> int:
        """Clear the name of every conversation a user owns, deleted or not.

        Part of erasure: a name is free text and may hold PII. Returns the
        number of rows touched.
        """
        return await conversation_repository.blank_names_for_user(session, user_id)


conversation_service = ConversationService()
