"""Tests for BaseAgent.get_stream_response — what reaches the client's stream."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from app.agents.base.agent import BaseAgent, _chunk_text
from app.agents.messages import Message

pytestmark = pytest.mark.unit


class _Agent(BaseAgent):
    async def create_graph(self, checkpointer):  # pragma: no cover - not used
        raise NotImplementedError


class _FakeGraph:
    """Emits what LangGraph's stream_mode="messages" emits: (message, metadata) pairs."""

    def __init__(self, items):
        self._items = items

    async def astream(self, *args, **kwargs):
        for item in self._items:
            yield item, {}

    async def aget_state(self, config):
        return SimpleNamespace(values={})


async def _collect(items) -> list[str]:
    agent = _Agent()
    agent._graph = _FakeGraph(items)
    with (
        patch("app.agents.base.agent.get_relevant_memory", new=AsyncMock(return_value="")),
        patch("app.agents.base.agent.update_memory", new=AsyncMock()),
    ):
        return [
            chunk
            async for chunk in agent.get_stream_response(
                [Message(role="user", content="hi")], uuid.uuid4(), user_id=uuid.uuid4()
            )
        ]


@pytest.mark.asyncio
async def test_tool_results_are_not_streamed():
    """A web-search result is a ToolMessage: it must not reach the user as reply text."""
    chunks = await _collect(
        [
            AIMessageChunk(content="Let me check. "),
            ToolMessage(content="RAW SEARCH RESULTS", tool_call_id="call_1"),
            AIMessageChunk(content="It is sunny."),
        ]
    )
    assert chunks == ["Let me check. ", "It is sunny."]


@pytest.mark.asyncio
async def test_empty_and_tool_call_chunks_are_skipped():
    chunks = await _collect([AIMessageChunk(content=""), AIMessageChunk(content="Hi")])
    assert chunks == ["Hi"]


@pytest.mark.asyncio
async def test_structured_content_is_flattened_to_text():
    """GPT-5 models stream content as a list of blocks; only text blocks are the answer."""
    chunks = await _collect(
        [AIMessageChunk(content=[{"type": "reasoning", "id": "r1"}, {"type": "text", "text": "Hello"}])]
    )
    assert chunks == ["Hello"]


@pytest.mark.asyncio
async def test_a_new_model_message_starts_a_new_paragraph():
    """Text written before a tool call and the answer after it are two messages, not one run-on line."""
    chunks = await _collect(
        [
            AIMessageChunk(content="Let me check", id="m1"),
            AIMessageChunk(content=" your spending.", id="m1"),
            ToolMessage(content="RAW", tool_call_id="call_1"),
            AIMessageChunk(content="You spent €40.", id="m2"),
        ]
    )
    assert "".join(chunks) == "Let me check your spending.\n\nYou spent €40."


@pytest.mark.asyncio
async def test_a_message_with_no_text_does_not_add_a_break():
    """A tool-call-only message streams nothing, so it must not leave a leading break."""
    chunks = await _collect(
        [
            AIMessageChunk(content="", id="m1"),
            ToolMessage(content="RAW", tool_call_id="call_1"),
            AIMessageChunk(content="You spent €40.", id="m2"),
        ]
    )
    assert "".join(chunks) == "You spent €40."


def test_history_joins_a_turns_assistant_messages_as_they_were_streamed():
    """The thread swaps the streamed reply for the history: they must read the same."""
    history = _Agent()._process_messages(
        [
            HumanMessage(content="How much did I spend?"),
            AIMessage(
                content="Let me check your spending.",
                tool_calls=[{"name": "search", "args": {}, "id": "call_1"}],
            ),
            ToolMessage(content="RAW", tool_call_id="call_1"),
            AIMessage(content="You spent €40."),
            HumanMessage(content="Thanks"),
            AIMessage(content="Any time."),
        ]
    )
    assert history == [
        Message(role="user", content="How much did I spend?"),
        Message(role="assistant", content="Let me check your spending.\n\nYou spent €40."),
        Message(role="user", content="Thanks"),
        Message(role="assistant", content="Any time."),
    ]


def test_chunk_text_handles_strings_and_blocks():
    assert _chunk_text("plain") == "plain"
    assert _chunk_text([{"type": "text", "text": "a"}, "b", {"type": "reasoning"}]) == "ab"
