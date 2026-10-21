"""Tests for app.modules.conversation.domain.chat — the stream events and the history the client sees."""

from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from app.agents.chatbot.middleware.tool_events import ToolCallFinished, ToolCallStarted
from app.modules.conversation.domain.chat import done, events, first_exchange, history
from app.modules.conversation.schemas import (
    Activity,
    ChatMessage,
    DoneEvent,
    ReasoningEvent,
    ReasoningPart,
    SummaryItem,
    TextEvent,
    ToolDisplay,
    ToolFinishedEvent,
    ToolPart,
    ToolStartedEvent,
)

pytestmark = pytest.mark.unit

DISPLAY = ToolDisplay(
    title="Spending by category",
    period="Sep 2026",
    summary=[SummaryItem(kind="count", value=14, label="categories")],
    table=None,
)

TITLES = {"spending": "Spending by category", "income": "Income"}


async def _graph_stream(items):
    """What `ChatbotAgent.stream` yields: (mode, payload) pairs.

    A bare AI message is a "messages" item from the model node, a ToolMessage one from the
    tools node; a (message, node) pair names another node; anything else is a "custom" item.
    """
    for item in items:
        if isinstance(item, tuple):
            message, node = item
            yield "messages", (message, {"langgraph_node": node})
        elif isinstance(item, AIMessage | ToolMessage):
            node = "tools" if isinstance(item, ToolMessage) else "model"
            yield "messages", (item, {"langgraph_node": node})
        else:
            yield "custom", item


async def _collect(items, titles=TITLES) -> list:
    return [event async for event in events(_graph_stream(items), titles)]


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


async def test_a_text_turn_streams_its_text_and_no_done():
    """`done` is the route's: it reads the saved state after the stream."""
    assert await _collect([AIMessageChunk(content="Hi", id="m1")]) == [TextEvent(text="Hi")]


async def test_tool_events_become_wire_events_in_order():
    events = await _collect(
        [
            AIMessageChunk(content="", id="m1"),
            ToolCallStarted(id="c1", name="spending"),
            ToolCallFinished(id="c1", ok=True, artifact=DISPLAY.model_dump()),
            ToolMessage(content="RAW", tool_call_id="c1"),
            AIMessageChunk(content="You spent €40.", id="m2"),
        ]
    )
    assert events == [
        ToolStartedEvent(id="c1", name="spending", title="Spending by category"),
        ToolFinishedEvent(id="c1", ok=True, display=DISPLAY),
        TextEvent(text="You spent €40."),
    ]


async def test_a_failed_call_finishes_without_a_display():
    events = await _collect([ToolCallFinished(id="c1", ok=False, artifact=None)])
    assert events == [ToolFinishedEvent(id="c1", ok=False, display=None)]


async def test_an_artifact_that_does_not_validate_streams_a_null_display():
    """Review Focus 3: the row still finishes, without figures, and the stream goes on."""
    with patch("app.modules.conversation.domain.chat.logger") as log:
        events = await _collect(
            [ToolCallFinished(id="c1", ok=True, artifact={"bogus": 1}), AIMessageChunk(content="OK", id="m2")]
        )
    assert events == [ToolFinishedEvent(id="c1", ok=True, display=None), TextEvent(text="OK")]
    assert log.warning.call_args.args[0] == "chat_stream_tool_display_invalid"
    assert log.warning.call_args.kwargs["tool_call_id"] == "c1"


async def test_a_started_event_for_a_name_without_a_title_yields_nothing():
    assert await _collect([ToolCallStarted(id="c1", name="invented")]) == []


async def test_a_tool_message_without_events_is_tolerated():
    """An unknown tool name emits no events; its ToolMessage still passes through the stream."""
    events = await _collect(
        [ToolMessage(content="That tool does not exist.", tool_call_id="c1"), AIMessageChunk(content="OK", id="m2")]
    )
    assert events == [TextEvent(text="OK")]


async def test_empty_chunks_are_skipped():
    events = await _collect([AIMessageChunk(content="", id="m1"), AIMessageChunk(content="Hi", id="m1")])
    assert events == [TextEvent(text="Hi")]


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
    """The first chunk opens an empty summary; later chunks carry text deltas (spike 1's raw content shape)."""
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
            ToolCallStarted(id="c1", name="spending"),
            _summary_chunk("After.", id="m2"),
        ]
    )
    assert [e.text for e in events if isinstance(e, ReasoningEvent)] == ["Before.", "After."]


async def test_a_reasoning_delta_after_a_text_event_starts_a_new_paragraph():
    """The separator fix: a wrap-up's reasoning after streamed text begins a new paragraph."""
    events = await _collect(
        [
            _summary_chunk("Thinking.", id="m1"),
            AIMessageChunk(content="Some text.", id="m1"),
            _summary_chunk("Wrapping up.", id="m2"),
        ]
    )
    assert [e.text for e in events if isinstance(e, ReasoningEvent)] == ["Thinking.", "\n\nWrapping up."]


async def test_only_the_model_nodes_output_is_streamed():
    """Another LLM call inside the graph must not reach the user."""
    events = await _collect(
        [(AIMessageChunk(content="internal", id="x"), "SummaryMiddleware.before_model"), AIMessageChunk(content="Hi")]
    )
    assert _text(events) == "Hi"


def test_done_is_stopped_only_when_the_last_message_is_in_stopped():
    earlier = AIMessage(content="Partial.", id="earlier")
    final = AIMessage(content="Full answer.", id="final")
    assert done([HumanMessage(content="hi"), final], {"final": "step_limit"}) == DoneEvent(stopped=True)
    assert done(
        [HumanMessage(content="a"), earlier, HumanMessage(content="b"), final], {"earlier": "repeated_call"}
    ) == DoneEvent(stopped=False)
    assert done([], {}) == DoneEvent(stopped=False)


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
    [user, reply] = history(_tool_turn(), {}, TITLES)
    assert user == ChatMessage(role="user", content="Where did my money go?")
    assert reply.content == "answer"
    assert reply.activity == Activity(
        parts=[ToolPart(id="c1", name="spending", title="Spending by category", ok=True, display=DISPLAY)]
    )


def test_history_drops_the_activity_of_an_unanswered_turn():
    """A turn the user stopped mid-tool reopens as the question alone."""
    assert [m.role for m in history(_tool_turn(answer=None), {}, TITLES)] == ["user"]


def test_history_drops_a_turn_whose_only_text_came_before_its_tool_call():
    messages = [
        HumanMessage(content="Q"),
        AIMessage(content="Let me check.", tool_calls=[{"name": "spending", "args": {}, "id": "c1"}]),
    ]
    assert [m.role for m in history(messages, {}, TITLES)] == ["user"]


def test_an_unanswered_turn_does_not_affect_the_next_one():
    messages = [*_tool_turn(answer=None), HumanMessage(content="Try again"), AIMessage(content="Here.")]
    assert history(messages, {}, TITLES) == [
        ChatMessage(role="user", content="Where did my money go?"),
        ChatMessage(role="user", content="Try again"),
        ChatMessage(role="assistant", content="Here."),
    ]


def test_history_marks_server_stopped_turns():
    [_, reply] = history(_tool_turn(), {"a2": "step_limit"}, TITLES)
    assert reply.activity.stopped is True


def test_a_reply_without_reasoning_or_tools_has_no_activity():
    reply = history([HumanMessage(content="Hi"), AIMessage(content="Hello.")], {}, TITLES)[-1]
    assert reply == ChatMessage(role="assistant", content="Hello.", activity=None)


def test_a_failed_tool_call_is_a_part_without_display_but_with_its_title():
    [_, reply] = history(_tool_turn(artifact=None, status="error"), {}, TITLES)
    assert reply.activity.parts == [
        ToolPart(id="c1", name="spending", title="Spending by category", ok=False, display=None)
    ]


def test_an_artifact_that_no_longer_validates_keeps_the_part_without_display():
    """An old checkpoint's artifact must not fail the whole history."""
    with patch("app.modules.conversation.domain.chat.logger") as log:
        [_, reply] = history(_tool_turn(artifact={"title": "Old shape"}), {}, TITLES)
    assert reply.activity.parts == [
        ToolPart(id="c1", name="spending", title="Spending by category", ok=True, display=None)
    ]
    assert log.warning.call_args.args[0] == "chat_history_tool_display_invalid"


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
    [_, reply] = history(messages, {}, TITLES)
    assert reply == ChatMessage(
        role="assistant",
        content="Answer.",
        activity=Activity(
            parts=[
                ReasoningPart(text="First.\n\nSecond."),
                ToolPart(id="c1", name="spending", title="Spending by category", ok=True, display=DISPLAY),
                ToolPart(id="c2", name="income", title="Income", ok=False, display=None),
                ReasoningPart(text="Then."),
            ]
        ),
    )


def test_an_empty_reasoning_summary_adds_no_part():
    messages = [
        HumanMessage(content="Hi"),
        AIMessage(content=[{"type": "reasoning", "id": "rs", "summary": []}, {"type": "text", "text": "Hello."}]),
    ]
    assert history(messages, {}, TITLES)[-1].activity is None


def test_history_joins_a_turns_assistant_messages_as_they_were_streamed():
    """The thread swaps the streamed reply for the history: they must read the same."""
    messages = [
        HumanMessage(content="How much did I spend?"),
        AIMessage(content="Let me check your spending.", tool_calls=[{"name": "search", "args": {}, "id": "call_1"}]),
        ToolMessage(content="RAW", tool_call_id="call_1", artifact=DISPLAY.model_dump()),
        AIMessage(content="You spent €40."),
        HumanMessage(content="Thanks"),
        AIMessage(content="Any time."),
    ]
    assert [(m.role, m.content) for m in history(messages, {}, {"search": "Search"})] == [
        ("user", "How much did I spend?"),
        ("assistant", "Let me check your spending.\n\nYou spent €40."),
        ("user", "Thanks"),
        ("assistant", "Any time."),
    ]


def test_a_tool_without_a_title_is_left_out():
    """The stream announces only the agent's own tools; the history matches it."""
    [_, reply] = history(_tool_turn(), {}, {"income": "Income"})
    assert reply.activity is None


def test_first_exchange_pairs_the_first_reply_with_the_question_it_answered():
    # A first turn stopped before any reply leaves its question unanswered:
    # the title must not pair it with the second turn's answer.
    messages = [
        ChatMessage(role="user", content="stopped question"),
        ChatMessage(role="user", content="answered question"),
        ChatMessage(role="assistant", content="the answer"),
        ChatMessage(role="user", content="a follow-up"),
    ]
    assert first_exchange(messages) == ("answered question", "the answer")


def test_first_exchange_is_none_before_any_reply():
    assert first_exchange([ChatMessage(role="user", content="hi")]) is None
