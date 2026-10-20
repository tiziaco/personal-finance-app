"""Conversation and chat request/response schemas."""

import re
import uuid
from datetime import datetime
from typing import List

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)

from app.agents.messages import ChatMessage


class ConversationResponse(BaseModel):
    """Response model for conversation operations.

    Attributes:
        conversation_id: The unique identifier for the chat conversation
        name: Name of the conversation (defaults to empty string)
        created_at: When the conversation was created
    """

    conversation_id: uuid.UUID = Field(..., description="The unique identifier for the chat conversation")
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

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Reject script tags and null bytes in what the user sends."""
        if re.search(r"<script.*?>.*?</script>", v, re.IGNORECASE | re.DOTALL):
            raise ValueError("Content contains potentially harmful script tags")
        if "\0" in v:
            raise ValueError("Content contains null bytes")
        return v


class ChatResponse(BaseModel):
    """Response model for chat endpoint.

    Attributes:
        message: The assistant's response message.
    """

    message: ChatMessage = Field(..., description="The assistant's response message")


class ConversationHistory(BaseModel):
    """Response model for conversation history endpoint.

    Attributes:
        messages: List of all messages in the conversation.
    """

    messages: List[ChatMessage] = Field(
        ..., description="The conversation's messages: each user message, then the reply to it with its activity"
    )
