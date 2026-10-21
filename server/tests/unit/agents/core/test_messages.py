"""drop_unanswered_tool_calls: a tool call left without its result never reaches the model."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.core.messages import drop_unanswered_tool_calls

pytestmark = pytest.mark.unit


def _call(call_id: str) -> dict:
    return {"name": "web_search", "args": {"query": "rent"}, "id": call_id}


def test_an_answered_tool_call_is_kept():
    history = [
        HumanMessage(content="Rent prices?"),
        AIMessage(content="", tool_calls=[_call("call_1")]),
        ToolMessage(content="results", tool_call_id="call_1"),
        AIMessage(content="About 1200 EUR."),
    ]
    assert drop_unanswered_tool_calls(history) == history


def test_an_unanswered_tool_call_with_no_text_is_dropped():
    question, retry = HumanMessage(content="Rent prices?"), HumanMessage(content="Never mind")
    history = [question, AIMessage(content="", tool_calls=[_call("call_1")]), retry]
    assert drop_unanswered_tool_calls(history) == [question, retry]


def test_an_unanswered_tool_calls_text_is_kept_without_the_call():
    history = [
        HumanMessage(content="Rent prices?"),
        AIMessage(content="Let me check.", tool_calls=[_call("call_1")], id="m1"),
        HumanMessage(content="Never mind"),
    ]
    cleaned = drop_unanswered_tool_calls(history)
    assert [m.content for m in cleaned] == ["Rent prices?", "Let me check.", "Never mind"]
    assert cleaned[1].tool_calls == []
    assert cleaned[1].id == "m1"


def test_a_partly_answered_message_is_dropped_with_its_results():
    # The tool node answers every call of a message at once, so a partial
    # answer is not expected; if one appears, a lone ToolMessage is as
    # unacceptable to the provider as a lone call.
    history = [
        HumanMessage(content="Two searches"),
        AIMessage(content="", tool_calls=[_call("call_1"), _call("call_2")]),
        ToolMessage(content="first", tool_call_id="call_1"),
        HumanMessage(content="Next"),
    ]
    assert [m.content for m in drop_unanswered_tool_calls(history)] == ["Two searches", "Next"]
