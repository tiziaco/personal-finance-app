"""Conversation and chat request/response schemas."""

import re
import uuid
from datetime import datetime
from typing import Annotated, List, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


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


class _HistoryModel(BaseModel):
    # A field with a default is still always present in a response: the schema says
    # so, and the generated client types `type`, `parts` and `activity` as required.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class ReasoningPart(_HistoryModel):
    """The readable summary of the model's reasoning for one of a turn's model calls."""

    type: Literal["reasoning"] = "reasoning"
    text: str = Field(..., description="The reasoning summary, its parts separated by a blank line")


class ToolPart(_HistoryModel):
    """One tool call a reply made, as the chat shows it."""

    type: Literal["tool"] = "tool"
    id: str = Field(..., description="The tool call's id, as the stream's tool events carry it")
    name: str = Field(..., description="The tool's name")
    title: str = Field(..., description="The tool's display title, as the stream's tool_started event carries it")
    ok: bool = Field(..., description="Whether the call produced a result")
    display: ToolDisplay | None = Field(
        default=None,
        description="What the chat shows for the result; null when the call failed or its display can no longer be shown",
    )


ActivityPart = Annotated[Union[ReasoningPart, ToolPart], Field(discriminator="type")]


class Activity(_HistoryModel):
    """What the assistant did on the way to a reply: reasoning and tool calls, in order."""

    parts: list[ActivityPart] = Field(default_factory=list, description="Reasoning and tool parts, in order")
    stopped: bool = Field(default=False, description="Whether the server ended the turn (step cap or repeat)")


class ChatMessage(_HistoryModel):
    """One message of a conversation's history, as the client shows it.

    Output shape only: no length or content rules, so a long reply, or one quoting
    `<script>` in a code block, is returned as stored.
    """

    role: Literal["user", "assistant"] = Field(..., description="Who wrote the message")
    content: str = Field(..., description="The message text; for a reply, the text of the whole turn")
    activity: Activity | None = Field(
        default=None,
        description="A reply's reasoning and tool calls; null for a user message, and for a reply with neither that was not stopped",
    )


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


class TextEvent(BaseModel):
    """A chunk of the assistant's reply text."""

    type: Literal["text"] = "text"
    text: str


class ReasoningEvent(BaseModel):
    """A chunk of the model's readable reasoning."""

    type: Literal["reasoning"] = "reasoning"
    text: str


class ToolStartedEvent(BaseModel):
    """The model called a tool; `title` is the label shown while it runs."""

    type: Literal["tool_started"] = "tool_started"
    id: str
    name: str
    title: str


class ToolFinishedEvent(BaseModel):
    """A tool call ended; `display` is None when it failed."""

    type: Literal["tool_finished"] = "tool_finished"
    id: str
    ok: bool
    display: ToolDisplay | None = None


class DoneEvent(BaseModel):
    """The turn is over; `stopped` is true when the server cut it short (step cap or repeat)."""

    type: Literal["done"] = "done"
    stopped: bool = False


class ErrorEvent(BaseModel):
    """The turn failed and produced no answer."""

    type: Literal["error"] = "error"


StreamEvent = Annotated[
    Union[TextEvent, ReasoningEvent, ToolStartedEvent, ToolFinishedEvent, DoneEvent, ErrorEvent],
    Field(discriminator="type"),
]
r"""Typed events the chat stream carries: the wire contract of `POST /chatbot/chat/{id}/stream`.

The route is tagged `streaming`, so it is not in the generated client: these models
are the schema, and `web-app/apps/web/src/lib/chat/stream-chat.ts` mirrors them by
hand. Each event is one server-sent event, `data: <json>` followed by a blank line,
its JSON a model below told apart by `type`:

- `{"type": "reasoning", "text"}`: a delta of the model's readable reasoning. A
  break between summary paragraphs arrives as "\n\n" inside a delta, as the history's
  `ReasoningPart` joins them. Reasoning before and after a tool row are two parts.
- `{"type": "tool_started", "id", "name", "title"}`: a tool call began; `title` is
  the label shown while it runs. Only the agent's own tools are announced.
- `{"type": "tool_finished", "id", "ok", "display"}`: that call ended; `display`
  (a `ToolDisplay`: title, period, summary, table) is null when `ok` is false.
  Parallel calls finish in any order; `id` pairs the two events.
- `{"type": "text", "text"}`: a delta of the reply. A new model message in the turn
  starts with "\n\n", as the history's `content` joins them.
- `{"type": "done", "stopped"}`: the turn is over and saved, always last on success;
  `stopped` is true when the server cut it short (step cap or repeated call).
- `{"type": "error"}`: the turn failed and ends here, with no `done`. It carries no
  text: the client words the failure.

A client that disconnects cancels the turn; nothing more is sent.
"""
