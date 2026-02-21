"""Conversation management service."""

from typing import (
    List,
    Optional,
)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import logger
from app.models.conversation import Conversation
from app.services.conversation.exceptions import ConversationNotFoundError


class ConversationService:
    """Service for chat conversation management operations."""
    
    @staticmethod
    async def create_conversation(session: AsyncSession, conversation_id: str, user_id: str, name: str = "") -> Conversation:
        """Create a new chat conversation.
        
        Args:
            session: Database session
            conversation_id: The ID for the new conversation
            user_id: The ID of the user who owns the conversation (UUID string)
            name: Optional name for the conversation
            
        Returns:
            Conversation: The created conversation
        """
        conversation = Conversation(id=conversation_id, user_id=user_id, name=name)
        session.add(conversation)
        await session.flush()
        await session.refresh(conversation)
        
        logger.info("conversation_created", conversation_id=conversation_id, user_id=user_id, name=name)
        return conversation
    
    @staticmethod
    async def get_conversation(session: AsyncSession, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID.
        
        Args:
            session: Database session
            conversation_id: The ID of the conversation to retrieve
            
        Returns:
            Optional[Conversation]: The conversation if found
        """
        conversation = await session.get(Conversation, conversation_id)
        return conversation
    
    @staticmethod
    async def get_user_conversations(session: AsyncSession, user_id: str) -> List[Conversation]:
        """Get all conversations for a user.
        
        Args:
            session: Database session
            user_id: The ID of the user (UUID string)
            
        Returns:
            List[Conversation]: List of user's conversations
        """
        statement = select(Conversation).where(Conversation.user_id == user_id, Conversation.deleted_at.is_(None)).order_by(Conversation.created_at)
        result = await session.execute(statement)
        return list(result.scalars().all())
    
    @staticmethod
    async def update_conversation_name(session: AsyncSession, conversation_id: str, name: str) -> Conversation:
        """Update a conversation's name.
        
        Args:
            session: Database session
            conversation_id: The ID of the conversation to update
            name: The new name for the conversation
            
        Returns:
            Conversation: The updated conversation
            
        Raises:
            ConversationNotFoundError: If conversation is not found
        """
        conversation = await session.get(Conversation, conversation_id)
        if not conversation:
            raise ConversationNotFoundError(
                f"Conversation {conversation_id} not found",
                conversation_id=conversation_id
            )
        
        conversation.name = name
        session.add(conversation)
        await session.flush()
        await session.refresh(conversation)
        
        logger.info("conversation_name_updated", conversation_id=conversation_id, name=name)
        return conversation
    
    @staticmethod
    async def soft_delete_conversation(session: AsyncSession, conversation_id: str) -> bool:
        """Soft-delete a conversation by setting deleted_at.

        Args:
            session: Database session
            conversation_id: The ID of the conversation to soft-delete

        Returns:
            bool: True if soft-deletion was successful, False if not found
        """
        conversation = await session.get(Conversation, conversation_id)
        if not conversation:
            return False

        conversation.soft_delete()
        session.add(conversation)
        await session.flush()

        logger.info("conversation_soft_deleted", conversation_id=conversation_id)
        return True

    @staticmethod
    async def soft_delete_all_user_conversations(session: AsyncSession, user_id: str) -> list[str]:
        """Soft-delete all active conversations for a user.

        Returns the list of conversation IDs so the caller can clear
        LangGraph checkpoint data for each one.

        Args:
            session: Database session
            user_id: The ID of the user whose conversations to soft-delete

        Returns:
            List of conversation IDs that were soft-deleted
        """
        statement = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.deleted_at.is_(None),
        )
        result = await session.execute(statement)
        conversations = result.scalars().all()

        for conv in conversations:
            conv.soft_delete()
            session.add(conv)

        await session.flush()

        conversation_ids = [conv.id for conv in conversations]
        logger.info("all_user_conversations_soft_deleted", user_id=user_id, count=len(conversation_ids))
        return conversation_ids

    @staticmethod
    async def delete_conversation(session: AsyncSession, conversation_id: str) -> bool:
        """Delete a conversation by ID.
        
        Args:
            session: Database session
            conversation_id: The ID of the conversation to delete
            
        Returns:
            bool: True if deletion was successful
        """
        conversation = await session.get(Conversation, conversation_id)
        if not conversation:
            return False
        
        await session.delete(conversation)
        logger.info("conversation_deleted", conversation_id=conversation_id)
        return True


# Create singleton instance
conversation_service = ConversationService()
