"""Conversation and chat request/response schemas."""

from datetime import datetime
from typing import List

from pydantic import (
    BaseModel,
    Field,
)

from app.agents.messages import Message


class ConversationResponse(BaseModel):
    """Response model for conversation operations.

    Attributes:
        conversation_id: The unique identifier for the chat conversation
        name: Name of the conversation (defaults to empty string)
        created_at: When the conversation was created
    """

    conversation_id: str = Field(..., description="The unique identifier for the chat conversation")
    name: str = Field(default="", description="Name of the conversation")
    created_at: datetime = Field(..., description="When the conversation was created")


class ChatRequest(BaseModel):
    """Request model for chat endpoint.

    Attributes:
        message: The user's message to send.
    """

    message: str = Field(
        ...,
        description="The user's message content",
        min_length=1,
        max_length=3000,
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoint.

    Attributes:
        message: The assistant's response message.
    """

    message: Message = Field(..., description="The assistant's response message")


class ConversationHistory(BaseModel):
    """Response model for conversation history endpoint.

    Attributes:
        messages: List of all messages in the conversation.
    """

    messages: List[Message] = Field(..., description="List of all messages in the conversation")


class StreamResponse(BaseModel):
    """Response model for streaming chat endpoint.

    Attributes:
        content: The content of the current chunk.
        done: Whether the stream is complete.
    """

    content: str = Field(default="", description="The content of the current chunk")
    done: bool = Field(default=False, description="Whether the stream is complete")
