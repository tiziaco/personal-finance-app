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

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from app.agents.chatbot.toolkit import ToolDisplay


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
