"""User profile endpoints for the API.

This module provides endpoints for retrieving and managing the authenticated user's profile.
Authentication is handled by Clerk - there are no register/login endpoints.
"""

import asyncio

from fastapi import (
    APIRouter,
    Request,
)

from app.api.dependencies.agent import ChatbotAgentDep
from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.database import DbSession
from app.agents.shared.memory.factory import delete_user_memory
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.schemas.auth import UserResponse
from app.services.clerk import clerk_service
from app.services.conversation import conversation_service
from app.services.user import user_provider

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Retrieve the authenticated user's profile information. "
    "Creates the user in the database on first access (JIT provisioning).",
)
async def get_me(user: CurrentUser):
    """Get the current authenticated user's profile.

    Args:
        user: The authenticated user (resolved via JIT provisioning).

    Returns:
        UserResponse: The user's profile information.
    """
    return UserResponse.model_validate(user)


@router.delete(
    "/me",
    status_code=204,
    summary="Delete current user account (GDPR)",
    description="Permanently delete the authenticated user's account and all associated data. "
    "This action cannot be undone.",
)
@limiter.limit(settings.rate_limits.endpoints.CHAT[0])
async def delete_me(
    request: Request,
    user: CurrentUser,
    db_session: DbSession,
    agent: ChatbotAgentDep,
):
    """Delete the current user's account in a GDPR-compliant manner.

    Steps performed:
    1. Delete user from Clerk (invalidates all future JWTs)
    2. Soft-delete all conversation records + collect their IDs
    3. Clear LangGraph checkpoint data for each conversation (message PII)
    4. Delete mem0 long-term memory (extracted fact PII)
    5. Anonymize the user record in DB
    6. Invalidate the in-memory user cache

    Args:
        request: The FastAPI request object for rate limiting.
        user: The authenticated user.
        db_session: Database session.
        agent: The chatbot agent for clearing checkpoint data.
    """
    original_clerk_id = user.clerk_id  # capture before anonymize_user() replaces it

    # 1. Delete from Clerk so the JWT cannot be used to re-provision the account
    await asyncio.to_thread(clerk_service.delete_user, original_clerk_id)

    # 2. Soft-delete all active conversation records; get IDs for LangGraph cleanup
    conversation_ids = await conversation_service.soft_delete_all_user_conversations(
        db_session, user.id
    )

    # 3. Clear LangGraph checkpoint data for each conversation (actual messages = PII)
    for conv_id in conversation_ids:
        await agent.clear_chat_history(conv_id)

    # 4. Delete mem0 long-term memory (extracted user facts = PII)
    await delete_user_memory(user.id)

    # 5. Anonymize the user record (clears PII fields + nulls conversation names)
    # Eagerly load conversations so anonymize_user() can iterate them without
    # triggering a synchronous lazy load on an async session (MissingGreenlet).
    await db_session.refresh(user, attribute_names=["conversations"])
    user.anonymize_user()
    db_session.add(user)
    await db_session.commit()

    # 6. Invalidate in-memory cache after commit
    user_provider.invalidate_cache(original_clerk_id)

    logger.info(
        "user_deleted_gdpr_compliant",
        user_id=user.id,
        conversation_count=len(conversation_ids),
    )
