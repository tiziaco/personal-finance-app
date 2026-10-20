"""Tests for BaseAgent — what reaches the client's stream, and the history rebuilt from a checkpoint."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from app.agents.base.agent import BaseAgent
from app.agents.chatbot.events import (
    DoneEvent,
    ReasoningEvent,
    TextEvent,
    ToolFinishedEvent,
    ToolStartedEvent,
)
from app.agents.chatbot.toolkit import SummaryItem, ToolDisplay, TurnContext
from app.agents.messages import Activity, ChatMessage, Message, ReasoningPart, ToolPart

pytestmark = pytest.mark.unit

DISPLAY = ToolDisplay(
    title="Spending by category",
    period="Sep 2026",
    summary=[SummaryItem(kind="count", value=14, label="categories")],
    table=None,
)


class _Agent(BaseAgent):
    async def create_graph(self, checkpointer):  # pragma: no cover - not used
        raise NotImplementedError


class _FakeGraph:
    """Emits what LangGraph's stream_mode=["messages", "custom"] emits: (mode, payload) pairs.

    A bare message is a "messages" item from the chat node; a (message, node) pair names
    another node; anything else is a "custom" item.
    """

    def __init__(self, items, values=None):
        self._items = items
        self._values = values or {}
        self.inputs: list[dict] = []
        self.configs: list[dict] = []

    async def astream(self, graph_input, *, config, stream_mode):
        self.inputs.append(graph_input)
        self.configs.append(config)
        for item in self._items:
            if isinstance(item, tuple):
                message, node = item
                yield "messages", (message, {"langgraph_node": node})
            elif isinstance(item, AIMessage | ToolMessage):
                node = "tool_call" if isinstance(item, ToolMessage) else "chat"
                yield "messages", (item, {"langgraph_node": node})
            else:
                yield "custom", item

    async def ainvoke(self, input, config):
        self.inputs.append(input)
        self.configs.append(config)
        return self._values

    async def aget_state(self, config):
        return SimpleNamespace(values=self._values)


def _turn_context() -> TurnContext:
    return TurnContext(user_id=uuid.uuid4(), session_factory=MagicMock())


async def _collect(items, values=None, *, ctx: TurnContext | None = None) -> list:
    agent = _Agent()
    agent._graph = _FakeGraph(items, values)
    with (
        patch("app.agents.base.agent.get_relevant_memory", new=AsyncMock(return_value="")),
        patch("app.agents.base.agent.update_memory", new=AsyncMock()),
    ):
        return [
            event
            async for event in agent.get_stream_response(
                [Message(role="user", content="hi")], uuid.uuid4(), ctx or _turn_context()
            )
        ]


def _text(events) -> str:
    return "".join(e.text for e in events if isinstance(e, TextEvent))


def _reasoning(events) -> str:
    return "".join(e.text for e in events if isinstance(e, ReasoningEvent))


def _summary_chunk(text: str, *, id: str = "m1", summary_index: int = 0) -> AIMessageChunk:
    return AIMessageChunk(
        content=[
            {
                "type": "reasoning",
                "index": 0,
                "summary": [{"index": summary_index, "type": "summary_text", "text": text}],
            }
        ],
        id=id,
    )


# ── The stream ────────────────────────────────────────────────────────────────


async def test_tool_results_are_not_streamed():
    """A tool's result is a ToolMessage: it must not reach the user as reply text."""
    events = await _collect(
        [
            AIMessageChunk(content="Let me check. ", id="m1"),
            ToolMessage(content="RAW RESULTS", tool_call_id="call_1"),
            AIMessageChunk(content="It is €40.", id="m2"),
        ]
    )
    assert "RAW" not in _text(events)


async def test_the_stream_ends_with_done():
    events = await _collect([AIMessageChunk(content="Hi", id="m1")])
    assert events == [TextEvent(text="Hi"), DoneEvent(stopped=False)]


async def test_tool_events_from_the_tool_node_pass_through_in_order():
    started = ToolStartedEvent(id="c1", name="spending", title="Looking up spending")
    finished = ToolFinishedEvent(id="c1", ok=True, display=DISPLAY)
    events = await _collect(
        [
            AIMessageChunk(content="", id="m1"),
            started,
            finished,
            ToolMessage(content="RAW", tool_call_id="c1"),
            AIMessageChunk(content="You spent €40.", id="m2"),
        ]
    )
    assert events == [started, finished, TextEvent(text="You spent €40."), DoneEvent()]


async def test_a_tool_message_without_events_is_tolerated():
    """An unknown tool name emits no events; its ToolMessage still passes through the stream."""
    events = await _collect(
        [ToolMessage(content="That tool does not exist.", tool_call_id="c1"), AIMessageChunk(content="OK", id="m2")]
    )
    assert events == [TextEvent(text="OK"), DoneEvent()]


async def test_empty_chunks_are_skipped():
    events = await _collect([AIMessageChunk(content="", id="m1"), AIMessageChunk(content="Hi", id="m1")])
    assert events == [TextEvent(text="Hi"), DoneEvent()]


async def test_only_text_blocks_are_reply_text():
    """GPT-5 sends content as blocks; only the text blocks are the reply."""
    events = await _collect(
        [AIMessageChunk(content=[{"type": "reasoning", "id": "r1", "summary": []}, {"type": "text", "text": "Hi"}])]
    )
    assert _text(events) == "Hi"


async def test_a_new_model_message_starts_a_new_paragraph():
    """Text written before a tool call and the answer after it are two messages, not one run-on line."""
    events = await _collect(
        [
            AIMessageChunk(content="Let me check", id="m1"),
            AIMessageChunk(content=" your spending.", id="m1"),
            ToolMessage(content="RAW", tool_call_id="call_1"),
            AIMessageChunk(content="You spent €40.", id="m2"),
        ]
    )
    assert _text(events) == "Let me check your spending.\n\nYou spent €40."


async def test_a_message_with_no_text_does_not_add_a_break():
    """A tool-call-only message streams nothing, so it must not leave a leading break."""
    events = await _collect(
        [
            AIMessageChunk(content="", id="m1"),
            ToolMessage(content="RAW", tool_call_id="call_1"),
            AIMessageChunk(content="You spent €40.", id="m2"),
        ]
    )
    assert _text(events) == "You spent €40."


async def test_reasoning_summary_deltas_stream_as_reasoning():
    """Spike outcome A: the first chunk opens an empty summary; later chunks carry text deltas."""
    events = await _collect(
        [
            AIMessageChunk(content=[{"type": "reasoning", "index": 0, "id": "rs_1", "summary": []}], id="m1"),
            _summary_chunk("**Checking**\n\nI"),
            _summary_chunk(" need"),
            _summary_chunk(""),
            AIMessageChunk(content=[{"type": "text", "text": "Done."}], id="m1"),
        ]
    )
    assert events == [
        ReasoningEvent(text="**Checking**\n\nI"),
        ReasoningEvent(text=" need"),
        TextEvent(text="Done."),
        DoneEvent(),
    ]


async def test_a_new_summary_part_starts_a_new_paragraph():
    """The history joins a message's summary parts with a blank line, so the stream does too."""
    events = await _collect([_summary_chunk("One."), _summary_chunk("Two.", summary_index=1)])
    assert _reasoning(events) == "One.\n\nTwo."


async def test_reasoning_after_a_tool_starts_fresh():
    """Reasoning on either side of a tool row is two parts: no break is added before the second."""
    events = await _collect(
        [
            _summary_chunk("Before.", id="m1"),
            ToolStartedEvent(id="c1", name="spending", title="Looking up spending"),
            _summary_chunk("After.", id="m2"),
        ]
    )
    assert [e.text for e in events if isinstance(e, ReasoningEvent)] == ["Before.", "After."]


async def test_only_the_chat_nodes_model_output_is_streamed():
    """Another LLM call inside the graph must not reach the user."""
    events = await _collect([(AIMessageChunk(content="internal", id="x"), "memory"), AIMessageChunk(content="Hi")])
    assert _text(events) == "Hi"


async def test_done_is_stopped_when_the_server_ended_the_turn():
    final = AIMessage(content="Partial answer.", id="final")
    events = await _collect(
        [final],
        values={"messages": [HumanMessage(content="hi"), final], "stopped": {"final": "step_limit"}},
    )
    assert events[-1] == DoneEvent(stopped=True)


async def test_done_is_not_stopped_for_an_earlier_stopped_turn():
    earlier = AIMessage(content="Partial.", id="earlier")
    final = AIMessage(content="Full answer.", id="final")
    events = await _collect(
        [final],
        values={
            "messages": [HumanMessage(content="a"), earlier, HumanMessage(content="b"), final],
            "stopped": {"earlier": "repeated_call"},
        },
    )
    assert events[-1] == DoneEvent(stopped=False)


async def test_stream_input_resets_turn_steps_and_carries_the_turn_context():
    ctx = _turn_context()
    agent = _Agent()
    agent._graph = _FakeGraph([AIMessageChunk(content="Hi")])
    with (
        patch("app.agents.base.agent.get_relevant_memory", new=AsyncMock(return_value="")),
        patch("app.agents.base.agent.update_memory", new=AsyncMock()),
    ):
        _ = [e async for e in agent.get_stream_response([Message(role="user", content="hi")], uuid.uuid4(), ctx)]
    assert agent._graph.inputs[0]["turn_steps"] == 0
    assert agent._graph.configs[0]["configurable"]["turn_context"] is ctx


async def test_get_response_input_resets_turn_steps_and_carries_the_turn_context():
    ctx = _turn_context()
    agent = _Agent()
    agent._graph = _FakeGraph([], values={"messages": [HumanMessage(content="hi"), AIMessage(content="Hello.")]})
    with (
        patch("app.agents.base.agent.get_relevant_memory", new=AsyncMock(return_value="")),
        patch("app.agents.base.agent.update_memory", new=AsyncMock()),
    ):
        result = await agent.get_response([Message(role="user", content="hi")], uuid.uuid4(), ctx)
    assert agent._graph.inputs[0]["turn_steps"] == 0
    assert agent._graph.configs[0]["configurable"]["turn_context"] is ctx
    assert result[-1] == ChatMessage(role="assistant", content="Hello.")


# ── The history ───────────────────────────────────────────────────────────────


def _tool_turn(*, artifact=DISPLAY.model_dump(), status: str = "success", answer: str | None = "answer"):
    messages = [
        HumanMessage(content="Where did my money go?"),
        AIMessage(content="", tool_calls=[{"name": "spending", "args": {}, "id": "c1"}], id="a1"),
        ToolMessage(content="RAW", tool_call_id="c1", artifact=artifact, status=status),
    ]
    if answer is not None:
        messages.append(AIMessage(content=answer, id="a2"))
    return messages


def test_history_folds_a_turn_into_one_message_with_activity():
    [user, reply] = _Agent()._process_messages(_tool_turn(), stopped={})
    assert user == ChatMessage(role="user", content="Where did my money go?")
    assert reply.content == "answer"
    assert reply.activity == Activity(parts=[ToolPart(id="c1", name="spending", ok=True, display=DISPLAY)])
    assert reply.activity.parts[0].display.title == "Spending by category"


def test_history_drops_the_activity_of_an_unanswered_turn():
    """Review Focus 1: a turn the user stopped mid-tool reopens as the question alone."""
    assert [m.role for m in _Agent()._process_messages(_tool_turn(answer=None), stopped={})] == ["user"]


def test_history_drops_a_turn_whose_only_text_came_before_its_tool_call():
    messages = [
        HumanMessage(content="Q"),
        AIMessage(content="Let me check.", tool_calls=[{"name": "spending", "args": {}, "id": "c1"}]),
    ]
    assert [m.role for m in _Agent()._process_messages(messages, stopped={})] == ["user"]


def test_an_unanswered_turn_does_not_affect_the_next_one():
    messages = [*_tool_turn(answer=None), HumanMessage(content="Try again"), AIMessage(content="Here.")]
    assert _Agent()._process_messages(messages, stopped={}) == [
        ChatMessage(role="user", content="Where did my money go?"),
        ChatMessage(role="user", content="Try again"),
        ChatMessage(role="assistant", content="Here."),
    ]


def test_history_marks_server_stopped_turns():
    [_, reply] = _Agent()._process_messages(_tool_turn(), stopped={"a2": "step_limit"})
    assert reply.activity.stopped is True


def test_a_reply_without_reasoning_or_tools_has_no_activity():
    history = _Agent()._process_messages([HumanMessage(content="Hi"), AIMessage(content="Hello.")], stopped={})
    assert history[-1] == ChatMessage(role="assistant", content="Hello.", activity=None)


def test_a_failed_tool_call_is_a_part_without_display():
    [_, reply] = _Agent()._process_messages(_tool_turn(artifact=None, status="error"), stopped={})
    assert reply.activity.parts == [ToolPart(id="c1", name="spending", ok=False, display=None)]


def test_an_artifact_that_no_longer_validates_keeps_the_part_without_display():
    """An old checkpoint's artifact must not fail the whole history."""
    [_, reply] = _Agent()._process_messages(_tool_turn(artifact={"title": "Old shape"}), stopped={})
    assert reply.activity.parts == [ToolPart(id="c1", name="spending", ok=True, display=None)]


def test_reasoning_and_tool_parts_keep_their_order():
    messages = [
        HumanMessage(content="Q"),
        AIMessage(
            content=[
                {
                    "type": "reasoning",
                    "id": "rs_1",
                    "summary": [
                        {"type": "summary_text", "text": "First."},
                        {"type": "summary_text", "text": "Second."},
                    ],
                    "encrypted_content": "opaque",
                }
            ],
            tool_calls=[
                {"name": "spending", "args": {}, "id": "c1"},
                {"name": "income", "args": {}, "id": "c2"},
            ],
        ),
        ToolMessage(content="RAW", tool_call_id="c2", status="error"),
        ToolMessage(content="RAW", tool_call_id="c1", artifact=DISPLAY.model_dump()),
        AIMessage(
            content=[
                {"type": "reasoning", "id": "rs_2", "summary": [{"type": "summary_text", "text": "Then."}]},
                {"type": "text", "text": "Answer."},
            ]
        ),
    ]
    [_, reply] = _Agent()._process_messages(messages, stopped={})
    assert reply == ChatMessage(
        role="assistant",
        content="Answer.",
        activity=Activity(
            parts=[
                ReasoningPart(text="First.\n\nSecond."),
                ToolPart(id="c1", name="spending", ok=True, display=DISPLAY),
                ToolPart(id="c2", name="income", ok=False, display=None),
                ReasoningPart(text="Then."),
            ]
        ),
    )


def test_an_empty_reasoning_summary_adds_no_part():
    messages = [
        HumanMessage(content="Hi"),
        AIMessage(content=[{"type": "reasoning", "id": "rs", "summary": []}, {"type": "text", "text": "Hello."}]),
    ]
    assert _Agent()._process_messages(messages, stopped={})[-1].activity is None


def test_history_joins_a_turns_assistant_messages_as_they_were_streamed():
    """The thread swaps the streamed reply for the history: they must read the same."""
    history = _Agent()._process_messages(
        [
            HumanMessage(content="How much did I spend?"),
            AIMessage(
                content="Let me check your spending.",
                tool_calls=[{"name": "search", "args": {}, "id": "call_1"}],
            ),
            ToolMessage(content="RAW", tool_call_id="call_1", artifact=DISPLAY.model_dump()),
            AIMessage(content="You spent €40."),
            HumanMessage(content="Thanks"),
            AIMessage(content="Any time."),
        ],
        stopped={},
    )
    assert [(m.role, m.content) for m in history] == [
        ("user", "How much did I spend?"),
        ("assistant", "Let me check your spending.\n\nYou spent €40."),
        ("user", "Thanks"),
        ("assistant", "Any time."),
    ]


def test_a_tool_the_agent_does_not_show_is_left_out():
    """The stream announces only the agent's own tools; the history matches it."""

    class _Shows(_Agent):
        def _shows_tool(self, name: str) -> bool:
            return name != "spending"

    [_, reply] = _Shows()._process_messages(_tool_turn(), stopped={})
    assert reply.activity is None
