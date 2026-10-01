"""Conversation verification dependencies for FastAPI endpoints."""

import uuid
from typing import Annotated

from fastapi import (
    Depends,
    Path,
    Request,
)

from app.agents.chatbot.graph import ChatbotAgent
from app.database.dependencies import DbSession
from app.modules.account import CurrentUser
from app.modules.conversation.exceptions import ConversationAccessDeniedError, ConversationNotFoundError
from app.modules.conversation.models import Conversation
from app.modules.conversation.service import conversation_service


async def get_user_conversation(
    user: CurrentUser,
    db_session: DbSession,
    conversation_id: uuid.UUID = Path(...),
) -> Conversation:
    """Verify conversation exists and belongs to authenticated user.

    Args:
        conversation_id: The conversation ID from path parameter
        user: The authenticated user
        db_session: Database session

    Returns:
        Conversation: The verified conversation

    Raises:
        ConversationNotFoundError: If conversation not found
        ConversationAccessDeniedError: If access denied
    """
    conversation = await conversation_service.get_conversation(db_session, conversation_id)

    if not conversation or conversation.deleted_at is not None:
        raise ConversationNotFoundError(f"Conversation {conversation_id} not found", conversation_id=conversation_id)

    if conversation.user_id != user.id:
        raise ConversationAccessDeniedError(
            f"User {user.id} does not have access to conversation {conversation_id}",
            conversation_id=conversation_id,
            user_id=user.id,
        )

    return conversation


# Type alias for cleaner endpoint signatures
UserConversation = Annotated[Conversation, Depends(get_user_conversation)]


def get_chatbot_agent(request: Request) -> ChatbotAgent:
    """Get the chatbot agent from application state.

    Args:
        request: The FastAPI request object.

    Returns:
        ChatbotAgent: The initialized chatbot agent instance.

    Raises:
        RuntimeError: If agents not initialized in app state.
    """
    if not hasattr(request.app.state, "agents"):
        raise RuntimeError("Agents not initialized in application state")

    return request.app.state.agents["chatbot"]


# Type alias for dependency injection
ChatbotAgentDep = Annotated[ChatbotAgent, Depends(get_chatbot_agent)]
