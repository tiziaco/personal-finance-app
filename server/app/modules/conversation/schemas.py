"""Conversation and chat request/response schemas."""

import re
import uuid
from datetime import datetime
from typing import List, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
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


class _DisplayModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


SummaryKind = Literal["count", "text", "total", "share", "rate", "weekendBias"]
"""How the web shows a summary figure, as the analytics page shows the same one.

`total` is an amount as a decimal string, unsigned under a label that says its direction.
`share` and `rate` are percents, a rate coloured good or bad; `weekendBias` is the percent
a weekend day costs over a weekday, worded as a sentence.
"""

ColumnKind = Literal["text", "count", "date", "total", "net", "transaction", "share", "rate", "change"]
"""How the web shows a table cell. Amounts are decimal strings: a `total` unsigned, a `net`
signed and coloured, a `transaction` signed with income coloured. A `change` is a percent
change in spending, "new" when there was nothing before, or null with no period to compare.
"""


class SummaryItem(_DisplayModel):
    """One figure in a tool row's one-line summary, e.g. a count, an amount or a share."""

    kind: SummaryKind
    value: float | int | str
    label: str | None = None


class TableColumn(_DisplayModel):
    """A column of a tool result's table: the row key, its header and how to format it."""

    key: str
    label: str
    kind: ColumnKind


class ToolTable(_DisplayModel):
    """The figures behind a tool result, as values the client formats by column kind; bounded for the UI."""

    columns: list[TableColumn]
    rows: list[dict[str, str | float | int | None]]


class ToolDisplay(_DisplayModel):
    """What the chat UI shows for one tool call: a title, the period covered, a summary and an optional table."""

    title: str
    period: str | None
    summary: list[SummaryItem]
    table: ToolTable | None
