"""Conversation repository for database operations."""

from typing import (
    List,
    Optional,
)

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import logger
from app.modules.conversation.models import Conversation


class ConversationRepository:
    """Repository for conversation database operations."""

    @staticmethod
    async def create(session: AsyncSession, conversation_id: str, user_id: str, name: str = "") -> Conversation:
        """Insert a new conversation row."""
        conversation = Conversation(id=conversation_id, user_id=user_id, name=name)
        session.add(conversation)
        await session.flush()
        await session.refresh(conversation)

        logger.info("conversation_created", conversation_id=conversation_id, user_id=user_id, name=name)
        return conversation

    @staticmethod
    async def get_by_id(session: AsyncSession, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by primary key, soft-deleted rows included.

        `get_user_conversation` in `dependencies.py` does its own `deleted_at` check.
        """
        return await session.get(Conversation, conversation_id)

    @staticmethod
    async def list_active_for_user(session: AsyncSession, user_id: str) -> List[Conversation]:
        """A user's non-soft-deleted conversations, oldest first — the order `GET /conversations` publishes."""
        statement = (
            select(Conversation)
            .where(Conversation.user_id == user_id, Conversation.deleted_at.is_(None))
            .order_by(Conversation.created_at)
        )
        result = await session.execute(statement)
        return list(result.scalars().all())

    @staticmethod
    async def update_name(session: AsyncSession, conversation: Conversation, name: str) -> Conversation:
        """Set a loaded conversation's name and flush it."""
        conversation.name = name
        session.add(conversation)
        await session.flush()
        await session.refresh(conversation)

        logger.info("conversation_name_updated", conversation_id=conversation.id, name=name)
        return conversation

    @staticmethod
    async def soft_delete(session: AsyncSession, conversation_id: str) -> bool:
        """Stamp deleted_at on one conversation. False if there is no such row."""
        conversation = await session.get(Conversation, conversation_id)
        if not conversation:
            return False

        conversation.soft_delete()
        session.add(conversation)
        await session.flush()

        logger.info("conversation_soft_deleted", conversation_id=conversation_id)
        return True

    @staticmethod
    async def soft_delete_active_for_user(session: AsyncSession, user_id: str) -> list[str]:
        """Soft-delete a user's active conversations and return their IDs. One flush for the set."""
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
    async def blank_names_for_user(session: AsyncSession, user_id: str) -> int:
        """Clear the name on every conversation a user owns, soft-deleted included; return the row count.

        One UPDATE: the soft-deleted rows are ones no active-rows select loads.
        """
        result = await session.execute(update(Conversation).where(Conversation.user_id == user_id).values(name=""))
        logger.info("all_user_conversation_names_blanked", user_id=user_id, count=result.rowcount)
        return result.rowcount

    @staticmethod
    async def list_ids_for_user(session: AsyncSession, user_id: str) -> list[str]:
        """Every conversation id a user owns, soft-deleted included. Ids only — no rows are loaded."""
        result = await session.execute(select(Conversation.id).where(Conversation.user_id == user_id))
        return list(result.scalars().all())


conversation_repository = ConversationRepository()
