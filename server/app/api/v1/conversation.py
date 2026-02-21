import uuid
from typing import List

from fastapi import (
    APIRouter,
    Form,
    Request,
)

from app.api.dependencies.agent import ChatbotAgentDep
from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.conversation import UserConversation
from app.api.dependencies.database import DbSession
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.schemas.conversation import ConversationResponse
from app.services.conversation import conversation_service
from app.utils.sanitization import sanitize_string

router = APIRouter()


@router.post(
    "/conversation",
    response_model=ConversationResponse,
    summary="Create a new chat conversation",
    description="Initialize a new chat conversation for the authenticated user with a unique conversation ID."
)
@limiter.limit(settings.rate_limits.endpoints.CHAT[0])
async def create_conversation(request: Request, db_session: DbSession, user: CurrentUser):
    """Create a new chat conversation for the authenticated user.

    Args:
        request: The FastAPI request object for rate limiting.
        db_session: Database session
        user: The authenticated user

    Returns:
        ConversationResponse: The conversation ID, name, and creation timestamp
    """
    # Generate a unique conversation ID
    conversation_id = str(uuid.uuid4())

    # Create conversation in database
    conversation = await conversation_service.create_conversation(db_session, conversation_id, user.id)

    logger.info(
        "conversation_created",
        conversation_id=conversation_id,
        user_id=user.id,
        name=conversation.name,
    )

    return ConversationResponse(
        conversation_id=conversation_id,
        name=conversation.name,
        created_at=conversation.created_at,
    )


@router.patch(
    "/conversation/{conversation_id}/name",
    response_model=ConversationResponse,
    summary="Rename a chat conversation",
    description="Update the display name of an existing chat conversation."
)
@limiter.limit(settings.rate_limits.endpoints.CHAT[0])
async def update_conversation_name(
    request: Request,
    conversation: UserConversation,
    db_session: DbSession,
    name: str = Form(...),
):
    """Update a conversation's name.

    Args:
        request: The FastAPI request object for rate limiting.
        conversation: The verified user conversation
        db_session: Database session
        name: The new name for the conversation

    Returns:
        ConversationResponse: The updated conversation information
    """
    # Sanitize name input
    sanitized_name = sanitize_string(name)

    # Update the conversation name
    conversation = await conversation_service.update_conversation_name(db_session, conversation.id, sanitized_name)

    return ConversationResponse(
        conversation_id=conversation.id,
        name=conversation.name,
        created_at=conversation.created_at,
    )


@router.delete(
    "/conversation/{conversation_id}",
    summary="Delete a chat conversation",
    description="Remove a chat conversation and permanently delete all associated messages."
)
@limiter.limit(settings.rate_limits.endpoints.CHAT[0])
async def delete_conversation(
    request: Request,
    conversation: UserConversation,
    db_session: DbSession,
    user: CurrentUser,
    agent: ChatbotAgentDep,
):
    """Delete a conversation for the authenticated user.

    Clears all LangGraph checkpoint data (messages) then soft-deletes the
    conversation record.

    Args:
        request: The FastAPI request object for rate limiting.
        conversation: The verified user conversation
        db_session: Database session
        user: The authenticated user
        agent: The chatbot agent for clearing checkpoint data

    Returns:
        None
    """
    # Delete all messages from LangGraph checkpoint tables first
    await agent.clear_chat_history(conversation.id)

    # Soft-delete the conversation record
    await conversation_service.soft_delete_conversation(db_session, conversation.id)

    logger.info("conversation_deleted", conversation_id=conversation.id, user_id=user.id)


@router.get(
    "/conversations",
    response_model=List[ConversationResponse],
    summary="List all user chat conversations",
    description="Retrieve all chat conversations created by the authenticated user."
)
@limiter.limit(settings.rate_limits.endpoints.CHAT[0])
async def get_user_conversations(request: Request, db_session: DbSession, user: CurrentUser):
    """Get all conversations for the authenticated user.

    Args:
        request: The FastAPI request object for rate limiting.
        db_session: Database session
        user: The authenticated user

    Returns:
        List[ConversationResponse]: List of conversations
    """
    conversations = await conversation_service.get_user_conversations(db_session, user.id)
    return [
        ConversationResponse(
            conversation_id=sanitize_string(conversation.id),
            name=sanitize_string(conversation.name),
            created_at=conversation.created_at,
        )
        for conversation in conversations
    ]
