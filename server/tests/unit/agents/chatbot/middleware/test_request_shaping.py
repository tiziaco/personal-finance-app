"""Tests for app.agents.chatbot.middleware.request_shaping — what the chat model is sent each call."""

import datetime as dt
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from app.agents.chatbot.context import TurnContext
from app.agents.chatbot.middleware.request_shaping import (
    STUB_TEMPLATE,
    SUMMARY_PREFIX,
    RequestShapingMiddleware,
    count_tokens,
    render_turn_context,
    shape_turn,
    split_turns,
    turns_after,
)
from app.core.config import settings

pytestmark = pytest.mark.unit

MODULE = "app.agents.chatbot.middleware.request_shaping"
TODAY = dt.date(2026, 10, 20)


def _tool_turn(question: str, call_id: str, *, title="Spending by category", period="Sep 2026", result="x" * 50):
    """A finished turn: question, a tool call, its result (with a display artifact), the answer."""
    artifact = {"title": title, "period": period, "summary": [], "table": None}
    return [
        HumanMessage(content=question, id=f"h-{call_id}"),
        AIMessage(content="", tool_calls=[{"name": "category_breakdown", "args": {}, "id": call_id}]),
        ToolMessage(content=result, tool_call_id=call_id, name="category_breakdown", artifact=artifact),
        AIMessage(content=f"answer to {question}", id=f"a-{call_id}"),
    ]


def _reasoning(text="thinking"):
    return {"type": "reasoning", "summary": [{"type": "summary_text", "text": text}], "encrypted_content": "enc"}


async def _shape(
    messages, *, state=None, preamble="preamble text", budget=None, monkeypatch=None
) -> list[BaseMessage]:
    """Run the middleware over `messages`; return the messages the handler (the model) receives."""
    if budget is not None:
        monkeypatch.setattr(settings.llm, "CHAT_HISTORY_MAX_TOKENS", budget)

    async def get_preamble(ctx):
        if isinstance(preamble, Exception):
            raise preamble
        return preamble

    seen: list[ModelRequest] = []

    async def handler(request):
        seen.append(request)
        return ModelResponse(result=[AIMessage("ok")])

    request = ModelRequest(
        model=MagicMock(),
        messages=messages,
        system_message=SystemMessage("sys"),
        tool_choice=None,
        tools=[],
        response_format=None,
        state={"messages": messages, **(state or {})},
        runtime=SimpleNamespace(context=TurnContext(user_id=MagicMock(), session_factory=MagicMock())),
        model_settings={},
    )
    with patch(f"{MODULE}.get_config", return_value={"configurable": {"thread_id": "thread-1"}}):
        await RequestShapingMiddleware(get_preamble).awrap_model_call(request, handler)

    assert seen[0].system_message == SystemMessage("sys")
    return seen[0].messages


def _turn_context(out):
    return next(m for m in out if isinstance(m, SystemMessage))


async def test_current_turn_is_never_trimmed_even_over_budget(monkeypatch):
    current = [
        HumanMessage(content="now"),
        AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "c1"}]),
        ToolMessage(content="huge " * 1000, tool_call_id="c1", name="t"),
    ]

    out = await _shape([*_tool_turn("old", "o1"), *current], budget=1, monkeypatch=monkeypatch)

    assert out[-len(current) :] == current
    assert [m.text for m in out if isinstance(m, HumanMessage)] == ["now"]


async def test_current_turn_keeps_its_reasoning_blocks_and_full_tool_results():
    ai = AIMessage(
        content=[_reasoning(), {"type": "text", "text": "looking"}],
        tool_calls=[{"name": "t", "args": {}, "id": "c1"}],
    )
    tool = ToolMessage(content="full figures", tool_call_id="c1", name="t", artifact={"title": "T", "period": None})
    current = [HumanMessage(content="now"), ai, tool]

    out = await _shape(current)

    assert out[-3:] == current
    assert out[-2].content[0]["type"] == "reasoning"
    assert out[-1].content == "full figures"


async def test_a_history_without_a_human_message_is_all_current_turn():
    messages = [AIMessage(content="hello")]

    assert (await _shape(messages))[-1:] == messages


async def test_earlier_tool_results_become_stubs():
    history = _tool_turn("old", "o1")

    out = await _shape([*history, HumanMessage(content="now")])

    stub = next(m for m in out if isinstance(m, ToolMessage))
    assert (
        stub.content
        == "Spending by category · Sep 2026: result omitted from an earlier turn; call the tool again for figures."
    )
    assert stub.tool_call_id == "o1"
    assert stub.content == STUB_TEMPLATE.format(title="Spending by category", period=" · Sep 2026")


async def test_stub_without_a_period_has_none():
    history = _tool_turn("old", "o1", title="Net worth", period=None)

    out = await _shape([*history, HumanMessage(content="now")])

    assert next(m for m in out if isinstance(m, ToolMessage)).content.startswith("Net worth: result omitted")


async def test_error_result_without_artifact_is_stubbed_by_the_tool_name():
    history = [
        HumanMessage(content="old"),
        AIMessage(content="", tool_calls=[{"name": "search_transactions", "args": {}, "id": "o1"}]),
        ToolMessage(content="The tool failed", tool_call_id="o1", name="search_transactions", status="error"),
        AIMessage(content="sorry"),
    ]

    out = await _shape([*history, HumanMessage(content="now")])

    stub = next(m for m in out if isinstance(m, ToolMessage))
    assert stub.content == STUB_TEMPLATE.format(title="search_transactions", period="")


async def test_error_result_with_no_known_name_is_stubbed_as_tool():
    history = [
        HumanMessage(content="old"),
        AIMessage(content="", tool_calls=[{"name": "", "args": {}, "id": "o1"}]),
        ToolMessage(content="nope", tool_call_id="o1", status="error"),
    ]

    out = await _shape([*history, HumanMessage(content="now")])

    assert next(m for m in out if isinstance(m, ToolMessage)).content.startswith("Tool: result omitted")


async def test_reasoning_blocks_are_stripped_from_earlier_turns():
    history = [HumanMessage(content="old"), AIMessage(content=[_reasoning(), {"type": "text", "text": "the answer"}])]

    out = await _shape([*history, HumanMessage(content="now")])

    assert out[1].content == "the answer"


async def test_an_earlier_tool_call_message_emptied_by_stripping_stays_with_its_pair():
    call = {"name": "category_breakdown", "args": {}, "id": "o1"}
    history = [
        HumanMessage(content="old"),
        AIMessage(content=[_reasoning()], tool_calls=[call]),
        ToolMessage(
            content="r", tool_call_id="o1", name="category_breakdown", artifact={"title": "T", "period": None}
        ),
        AIMessage(content="done"),
    ]

    out = await _shape([*history, HumanMessage(content="now")])

    ai = out[1]
    assert isinstance(ai, AIMessage) and ai.content == "" and ai.tool_calls[0]["id"] == "o1"
    assert isinstance(out[2], ToolMessage) and out[2].tool_call_id == "o1"


async def test_oldest_turns_drop_first_and_tool_pairs_stay_whole(monkeypatch):
    history = [*_tool_turn("first", "a"), *_tool_turn("second", "b"), *_tool_turn("third", "c")]
    one_turn = count_tokens(shape_turn(_tool_turn("third", "c")))
    # Fits the newest turn and nothing older.
    budget = one_turn + 1

    out = await _shape([*history, HumanMessage(content="now")], budget=budget, monkeypatch=monkeypatch)

    assert [m.text for m in out if isinstance(m, HumanMessage)] == ["third", "now"]
    call_ids = {c["id"] for m in out if isinstance(m, AIMessage) for c in m.tool_calls}
    assert {m.tool_call_id for m in out if isinstance(m, ToolMessage)} <= call_ids


async def test_a_tool_call_without_a_result_is_not_sent():
    history = [
        HumanMessage(content="old"),
        AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "lost"}]),
    ]

    out = await _shape([*history, HumanMessage(content="now")])

    assert not any(isinstance(m, AIMessage) and m.tool_calls for m in out)


async def test_turn_context_comes_after_the_history_and_before_the_current_turn():
    current = [HumanMessage(content="now")]
    history = _tool_turn("old", "o1")

    out = await _shape([*history, *current])

    shaped = shape_turn(history)
    assert len(out) == len(shaped) + 2
    assert [m.text for m in out[: len(shaped)]] == [m.text for m in shaped]
    assert isinstance(out[-2], SystemMessage) and "Today's date" in out[-2].text
    assert out[-1] == current[0]


async def test_the_summary_comes_first_and_only_turns_after_the_cutoff_follow():
    first, second = _tool_turn("first", "a"), _tool_turn("second", "b")
    state = {"summary": "They asked about food.", "summary_through": first[-1].id}

    out = await _shape([*first, *second, HumanMessage(content="now")], state=state)

    assert out[0] == SystemMessage(SUMMARY_PREFIX + "They asked about food.")
    assert [m.text for m in out if isinstance(m, HumanMessage)] == ["second", "now"]


async def test_a_cutoff_id_that_is_not_in_the_history_means_no_cutoff():
    first, second = _tool_turn("first", "a"), _tool_turn("second", "b")

    out = await _shape([*first, *second, HumanMessage(content="now")], state={"summary_through": "gone"})

    assert [m.text for m in out if isinstance(m, HumanMessage)] == ["first", "second", "now"]
    assert not any(isinstance(m, SystemMessage) and m.text.startswith(SUMMARY_PREFIX) for m in out)


async def test_a_failed_preamble_still_shapes_the_request_and_logs():
    with patch(f"{MODULE}.logger") as log:
        out = await _shape([HumanMessage(content="now")], preamble=RuntimeError("boom"))

    assert out[-1].text == "now" and "Today's date" in _turn_context(out).text
    log.exception.assert_called_once()
    assert log.exception.call_args.args[0] == "chat_preamble_failed"
    assert log.exception.call_args.kwargs["thread_id"] == "thread-1"


async def test_the_turn_context_carries_date_preamble_and_memory():
    out = await _shape(
        [HumanMessage(content="now")], state={"long_term_memory": "Saving for a flat"}, preamble="Last month: Sep 2026"
    )

    text = _turn_context(out).text
    assert dt.date.today().isoformat() in text and "Last month: Sep 2026" in text and "Saving for a flat" in text


def test_render_turn_context_joins_three_sections_and_defaults_the_memory():
    text = render_turn_context(today=TODAY, memory="", preamble=" Last month: Sep 2026 ")

    sections = text.split("\n\n")
    assert sections[0] == "Today's date: 2026-10-20."
    assert sections[1] == "Last month: Sep 2026"
    assert sections[2].endswith("Nothing yet.")


def test_render_turn_context_without_preamble_has_two_sections():
    assert len(render_turn_context(today=TODAY, memory="m", preamble="").split("\n\n")) == 2


def test_split_turns_and_turns_after_are_pure_helpers():
    first, second = _tool_turn("first", "a"), _tool_turn("second", "b")
    earlier, current = split_turns([*first, *second, HumanMessage("now")])

    assert earlier == [first, second] and [m.text for m in current] == ["now"]
    assert turns_after(earlier, first[-1].id) == [second]
    assert turns_after(earlier, None) == earlier
    assert turns_after(earlier, "gone") == earlier


async def test_a_trailing_system_message_after_the_last_human_message_stays_last():
    wrap_up = SystemMessage("Tools are no longer available this turn.")

    out = await _shape([*_tool_turn("old", "o1"), HumanMessage(content="now"), wrap_up])

    assert out[-1] == wrap_up
    assert out[-2].text == "now"


async def test_shaping_does_not_mutate_the_state_messages():
    ai = AIMessage(
        content=[_reasoning(), {"type": "text", "text": "looking"}], tool_calls=[{"name": "t", "args": {}, "id": "c1"}]
    )
    tool = ToolMessage(content="full figures", tool_call_id="c1", name="t")
    messages = [HumanMessage(content="old", id="h1"), ai, tool, AIMessage(content="ok"), HumanMessage(content="now")]

    out = await _shape(messages)

    assert not any(isinstance(m.content, list) for m in out if isinstance(m, AIMessage))
    assert messages[1].content[0]["type"] == "reasoning"
    assert messages[2].content == "full figures"
