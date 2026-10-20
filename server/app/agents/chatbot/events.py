"""Typed events the chat stream carries (§8): the tool node's and the route's vocabulary."""

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
