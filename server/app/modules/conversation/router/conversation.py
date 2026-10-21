"""Conversation CRUD endpoints for the authenticated user."""

from typing import List

from fastapi import (
    APIRouter,
    Form,
    Request,
)

from app.agents.core import delete_conversation_checkpoints
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.database.dependencies import DbSession
from app.modules.account import CurrentUser
from app.modules.conversation.dependencies import ChatbotAgentDep, UserConversation
from app.modules.conversation.schemas import ConversationResponse
from app.modules.conversation.service import conversation_service

router = APIRouter(prefix="/conversation", tags=["conversation"])


@router.post(
    "/conversation",
    operation_id="createConversation",
    response_model=ConversationResponse,
    summary="Create a new chat conversation",
    description="Initialize a new chat conversation for the authenticated user with a unique conversation ID.",
)
@limiter.limit(settings.rate_limits.endpoints.CHAT[0])
async def create_conversation(request: Request, db_session: DbSession, user: CurrentUser):
    """Create a new chat conversation for the authenticated user."""
    conversation = await conversation_service.create_conversation(db_session, user.id)

    return ConversationResponse(
        conversation_id=conversation.id,
        name=conversation.name,
        created_at=conversation.created_at,
    )


@router.patch(
    "/conversation/{conversation_id}/name",
    operation_id="renameConversation",
    response_model=ConversationResponse,
    summary="Rename a chat conversation",
    description="Update the display name of an existing chat conversation.",
)
@limiter.limit(settings.rate_limits.endpoints.CHAT[0])
async def update_conversation_name(
    request: Request,
    conversation: UserConversation,
    db_session: DbSession,
    name: str = Form(..., max_length=100),
):
    """Update a conversation's name.

    Stored verbatim: JSON and React escape on output. Null bytes are dropped
    because Postgres text columns reject them.
    """
    conversation = await conversation_service.update_conversation_name(
        db_session, conversation.id, name.replace("\0", "")
    )

    return ConversationResponse(
        conversation_id=conversation.id,
        name=conversation.name,
        created_at=conversation.created_at,
    )


@router.delete(
    "/conversation/{conversation_id}",
    operation_id="deleteConversation",
    status_code=204,
    summary="Delete a chat conversation",
    description="Remove a chat conversation and permanently delete all associated messages.",
)
@limiter.limit(settings.rate_limits.endpoints.CHAT[0])
async def delete_conversation(
    request: Request,
    conversation: UserConversation,
    db_session: DbSession,
):
    """Delete a conversation for the authenticated user.

    Checkpoint data (the messages) is hard-deleted first; the conversation row
    is then soft-deleted.
    """
    await delete_conversation_checkpoints(conversation.id)
    await conversation_service.soft_delete_conversation(db_session, conversation.id)


@router.get(
    "/conversations",
    operation_id="listConversations",
    response_model=List[ConversationResponse],
    summary="List all user chat conversations",
    description="Retrieve all chat conversations created by the authenticated user.",
)
@limiter.limit(settings.rate_limits.endpoints.CHAT[0])
async def get_user_conversations(request: Request, db_session: DbSession, user: CurrentUser):
    """Get all conversations for the authenticated user."""
    conversations = await conversation_service.get_user_conversations(db_session, user.id)
    return [
        ConversationResponse(
            conversation_id=conversation.id,
            name=conversation.name,
            created_at=conversation.created_at,
        )
        for conversation in conversations
    ]


@router.post(
    "/conversation/{conversation_id}/title",
    operation_id="generateConversationTitle",
    response_model=ConversationResponse,
    summary="Generate a conversation title",
    description=(
        "Name an untitled conversation from its first exchange. A conversation that already "
        "has a name, or has no reply yet, is returned unchanged."
    ),
)
@limiter.limit(settings.rate_limits.endpoints.CHAT[0])
async def generate_conversation_title(
    request: Request,
    conversation: UserConversation,
    db_session: DbSession,
    agent: ChatbotAgentDep,
):
    """Generate and save a title for an untitled conversation."""
    conversation = await conversation_service.generate_title(db_session, conversation, agent)

    return ConversationResponse(
        conversation_id=conversation.id,
        name=conversation.name,
        created_at=conversation.created_at,
    )
