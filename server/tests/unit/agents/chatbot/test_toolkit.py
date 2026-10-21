"""Tests for app.agents.chatbot.toolkit — the contract tools are written against."""

import uuid
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, ValidationError

from app.agents.chatbot.events import DoneEvent, StreamEvent, ToolFinishedEvent
from app.agents.chatbot.toolkit import AgentTool, SummaryItem, ToolDisplay, Toolkit, TurnContext

pytestmark = pytest.mark.unit


class Args(BaseModel):
    n: int


async def test_empty_toolkit_has_no_tools_and_an_empty_preamble():
    toolkit = Toolkit.empty()
    ctx = TurnContext(user_id=uuid.uuid4(), session_factory=MagicMock())

    assert toolkit.tools == []
    assert await toolkit.preamble(ctx) == ""


def test_as_schema_is_an_openai_tool_schema_from_the_args_model():
    tool = AgentTool(name="t", title="T", description="Does t.", args_schema=Args, run=MagicMock())

    schema = tool.as_schema()

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "t"
    assert schema["function"]["description"] == "Does t."
    assert schema["function"]["parameters"]["required"] == ["n"]


def test_turn_context_history_slot_starts_empty():
    ctx = TurnContext(user_id=uuid.uuid4(), session_factory=MagicMock())

    assert ctx.history is None


def test_display_models_forbid_unknown_fields():
    with pytest.raises(ValidationError):
        SummaryItem(kind="count", value=1, extra="x")
    with pytest.raises(ValidationError):
        ToolDisplay(title="t", period=None, summary=[], table=None, extra="x")


def test_stream_events_are_discriminated_by_type():
    from pydantic import TypeAdapter

    adapter = TypeAdapter(StreamEvent)

    assert adapter.validate_python({"type": "done", "stopped": True}) == DoneEvent(stopped=True)
    assert isinstance(adapter.validate_python({"type": "tool_finished", "id": "c", "ok": False}), ToolFinishedEvent)
