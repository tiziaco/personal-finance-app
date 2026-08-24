"""Chatbot API endpoints for handling chat interactions.

This module provides endpoints for chat interactions, including regular chat,
streaming chat, message history management, and chat history clearing.
"""

import json
from typing import List

from fastapi import (
    APIRouter,
    Request,
)
from fastapi.responses import StreamingResponse

from app.api.dependencies.agent import ChatbotAgentDep
from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.conversation import UserConversation
from app.api.dependencies.database import DbSession
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.core.metrics import llm_stream_duration_seconds
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationHistory,
    Message,
    StreamResponse,
)

router = APIRouter()


@router.post(
    "/chat/{conversation_id}",
    response_model=ChatResponse,
    summary="Send a message and get a response",
    description="Process a chat message and return the AI agent's response."
)
@limiter.limit(settings.rate_limits.endpoints.CHAT[0])
async def chat(
    conversation: UserConversation,
    request: Request,
    chat_request: ChatRequest,
    user: CurrentUser,
    agent: ChatbotAgentDep,
):
    """Process a chat request using LangGraph.

    Args:
        conversation: The verified user conversation
        request: The FastAPI request object for rate limiting.
        chat_request: The chat request containing the user's message.
        user: The authenticated user.

    Returns:
        ChatResponse: The processed chat response.
    """
    logger.info(
        "chat_request_received",
        conversation_id=conversation.id,
        message_length=len(chat_request.message),
    )

    # Wrap single message in list for agent processing
    user_message = Message(role="user", content=chat_request.message)
    result = await agent.get_response([user_message], conversation.id, user_id=user.id)

    logger.info("chat_request_processed", conversation_id=conversation.id)

    return ChatResponse(message=result[-1])


@router.post(
    "/chat/{conversation_id}/stream",
    summary="Stream chat response in real-time",
    description="Send a message and receive the AI agent's response as a server-sent event stream."
)
@limiter.limit(settings.rate_limits.endpoints.CHAT_STREAM[0])
async def chat_stream(
    conversation: UserConversation,
    request: Request,
    chat_request: ChatRequest,
    user: CurrentUser,
    agent: ChatbotAgentDep,
):
    """Process a chat request using LangGraph with streaming response.

    Args:
        conversation: The verified user conversation
        request: The FastAPI request object for rate limiting.
        chat_request: The chat request containing the user's message.
        user: The authenticated user.

    Returns:
        StreamingResponse: A streaming response of the chat completion.
    """
    logger.info(
        "stream_chat_request_received",
        conversation_id=conversation.id,
        message_length=len(chat_request.message),
    )

    async def event_generator():
        """Generate streaming events.

        Yields:
            str: Server-sent events in JSON format.

        Raises:
            Exception: If there's an error during streaming.
        """
        try:
            full_response = ""
            # Wrap single message in list for agent processing
            user_message = Message(role="user", content=chat_request.message)
            with llm_stream_duration_seconds.labels(model=agent.llm_service.get_llm().get_name()).time():
                async for chunk in agent.get_stream_response(
                    [user_message], conversation.id, user_id=user.id
                ):
                    full_response += chunk
                    response = StreamResponse(content=chunk, done=False)
                    yield f"data: {json.dumps(response.model_dump())}\n\n"

            # Send final message indicating completion
            final_response = StreamResponse(content="", done=True)
            yield f"data: {json.dumps(final_response.model_dump())}\n\n"

        except Exception as e:
            logger.error(
                "stream_chat_request_failed",
                conversation_id=conversation.id,
                error=str(e),
                exc_info=True,
            )
            error_response = StreamResponse(content="An error occurred. Please try again.", done=True)
            yield f"data: {json.dumps(error_response.model_dump())}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get(
    "/chat/{conversation_id}/messages",
    response_model=ConversationHistory,
    summary="Get conversation chat history",
    description="Retrieve all messages from the specified chat conversation."
)
@limiter.limit(settings.rate_limits.endpoints.MESSAGES[0])
async def get_conversation_messages(
    conversation: UserConversation,
    request: Request,
    agent: ChatbotAgentDep,
):
    """Get all messages for a conversation.

    Args:
        conversation: The verified user conversation
        request: The FastAPI request object for rate limiting.

    Returns:
        ConversationHistory: All messages in the conversation.
    """
    messages = await agent.get_chat_history(conversation.id)
    return ConversationHistory(messages=messages)


@router.delete(
    "/chat/{conversation_id}/messages",
    summary="Clear chat history",
    description="Remove all messages from the specified chat conversation."
)
@limiter.limit(settings.rate_limits.endpoints.MESSAGES[0])
async def clear_chat_history(
    conversation: UserConversation,
    request: Request,
    agent: ChatbotAgentDep,
):
    """Clear all messages for a conversation.

    Args:
        conversation: The verified user conversation
        request: The FastAPI request object for rate limiting.

    Returns:
        dict: A message indicating the chat history was cleared.
    """
    await agent.clear_chat_history(conversation.id)
    return {"message": "Chat history cleared successfully"}
