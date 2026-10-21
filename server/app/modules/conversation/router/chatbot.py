"""Chatbot API endpoints for handling chat interactions."""

import asyncio

from fastapi import (
    APIRouter,
    Request,
)
from sse_starlette import EventSourceResponse

from app.agents.chatbot import TurnContext
from app.agents.core import delete_conversation_checkpoints
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.core.metrics import llm_stream_duration_seconds
from app.database.dependencies import DbSession, release_connection
from app.modules.account import CurrentUser
from app.modules.conversation.dependencies import ChatbotAgentDep, UserConversation
from app.modules.conversation.domain.chat import done, events, history
from app.modules.conversation.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationHistory,
    ErrorEvent,
)

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


@router.post(
    "/chat/{conversation_id}",
    operation_id="sendChatMessage",
    response_model=ChatResponse,
    summary="Send a message and get a response",
    description="Process a chat message and return the AI agent's response.",
)
@limiter.limit(settings.rate_limits.endpoints.CHAT[0])
async def chat(
    conversation: UserConversation,
    request: Request,
    chat_request: ChatRequest,
    user: CurrentUser,
    agent: ChatbotAgentDep,
    db_session: DbSession,
):
    """Process a chat request using LangGraph."""
    logger.info(
        "chat_request_received",
        conversation_id=conversation.id,
        message_length=len(chat_request.message),
    )

    await release_connection(db_session)
    turn_context = TurnContext(user_id=user.id, session_factory=request.app.state.session_factory)
    messages, stopped = await agent.run(chat_request.message, conversation.id, turn_context)

    logger.info("chat_request_processed", conversation_id=conversation.id)

    return ChatResponse(message=history(messages, stopped, agent.tool_titles)[-1])


@router.post(
    "/chat/{conversation_id}/stream",
    operation_id="streamChatMessage",
    tags=["streaming"],
    summary="Stream chat response in real-time",
    description="Send a message and receive the AI agent's response as a server-sent event stream.",
)
@limiter.limit(settings.rate_limits.endpoints.CHAT_STREAM[0])
async def chat_stream(
    conversation: UserConversation,
    request: Request,
    chat_request: ChatRequest,
    user: CurrentUser,
    agent: ChatbotAgentDep,
    db_session: DbSession,
):
    """Process a chat request using LangGraph, streaming the response."""
    logger.info(
        "stream_chat_request_received",
        conversation_id=conversation.id,
        message_length=len(chat_request.message),
    )

    # The stream takes seconds: hand the connection back first.
    await release_connection(db_session)

    # Plain values only: the body runs after the request's session has closed.
    turn_context = TurnContext(user_id=user.id, session_factory=request.app.state.session_factory)

    async def event_generator():
        """Yield the turn's events as server-sent events, one JSON payload each.

        The payloads are the stream events of `conversation.schemas`: the turn's
        events as `domain.chat.events` translates them, then `done` from the saved
        state, or `error` if the turn failed. An error carries no text: the client
        words it.

        Run by EventSourceResponse, which cancels this generator when the client
        disconnects. The CancelledError travels down into the agent and the HTTP
        call to the model, which is what stops a call nobody is waiting for.
        """
        try:
            with llm_stream_duration_seconds.labels(model=settings.llm.DEFAULT_LLM_MODEL).time():
                async for event in events(
                    agent.stream(chat_request.message, conversation.id, turn_context), agent.tool_titles
                ):
                    yield {"data": event.model_dump_json()}
                messages, stopped = await agent.state(conversation.id)
                yield {"data": done(messages, stopped).model_dump_json()}

        except asyncio.CancelledError:
            logger.info("stream_chat_client_disconnected", conversation_id=conversation.id)
            raise

        except Exception as e:
            logger.error(
                "stream_chat_request_failed",
                conversation_id=conversation.id,
                error=str(e),
                exc_info=True,
            )
            yield {"data": ErrorEvent().model_dump_json()}

    # sep="\n": "data: {...}\n\n" frames, the framing `stream-chat.ts` splits on.
    return EventSourceResponse(event_generator(), sep="\n")


@router.get(
    "/chat/{conversation_id}/messages",
    operation_id="listChatMessages",
    response_model=ConversationHistory,
    summary="Get conversation chat history",
    description="Retrieve all messages from the specified chat conversation.",
)
@limiter.limit(settings.rate_limits.endpoints.MESSAGES[0])
async def get_conversation_messages(
    conversation: UserConversation,
    request: Request,
    agent: ChatbotAgentDep,
):
    """Get all messages for a conversation."""
    return ConversationHistory(messages=history(*await agent.state(conversation.id), agent.tool_titles))


@router.delete(
    "/chat/{conversation_id}/messages",
    operation_id="clearChatHistory",
    status_code=204,
    summary="Clear chat history",
    description="Remove all messages from the specified chat conversation.",
)
@limiter.limit(settings.rate_limits.endpoints.MESSAGES[0])
async def clear_chat_history(
    conversation: UserConversation,
    request: Request,
):
    """Clear all messages for a conversation."""
    await delete_conversation_checkpoints(conversation.id)
