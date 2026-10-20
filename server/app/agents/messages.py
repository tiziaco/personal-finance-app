"""The messages exchanged with an agent: what goes in, and the history that comes out."""

from typing import (
    Annotated,
    Literal,
    Union,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.agents.chatbot.toolkit import ToolDisplay


class Message(BaseModel):
    """A message sent to an agent: the turn's input.

    The rules on what a user may send (length, script tags, null bytes) live on
    `ChatRequest`; this carries what passed them.

    Attributes:
        role: The role of the message sender (user, assistant or system).
        content: The content of the message.
    """

    model_config = {"extra": "ignore"}

    role: Literal["user", "assistant", "system"] = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The content of the message", min_length=1)


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
