"""Tests for app.agents.chatbot.context — what the chat model is sent."""

import datetime as dt

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from app.agents.chatbot.context import (
    STUB_TEMPLATE,
    build_model_context,
    estimate_tokens,
    render_turn_context,
    with_estimate_fallback,
)
from app.agents.chatbot.prompts import load_system_prompt
from app.integrations.llm.service import LLMRegistry

pytestmark = pytest.mark.unit

PROMPT = "static prompt"
TURN_CONTEXT = "turn context"


def _chars(messages: list[BaseMessage]) -> int:
    return sum(len(m.text) for m in messages)


def _build(messages, budget=10_000, count=_chars):
    return build_model_context(
        messages, system_prompt=PROMPT, turn_context_text=TURN_CONTEXT, budget_tokens=budget, count_tokens=count
    )


def _tool_turn(question: str, call_id: str, *, title="Spending by category", period="Sep 2026", result="x" * 50):
    """A finished turn: question, a tool call, its result (with a display artifact), the answer."""
    artifact = {"title": title, "period": period, "summary": [], "table": None}
    return [
        HumanMessage(content=question),
        AIMessage(content="", tool_calls=[{"name": "category_breakdown", "args": {}, "id": call_id}]),
        ToolMessage(content=result, tool_call_id=call_id, name="category_breakdown", artifact=artifact),
        AIMessage(content=f"answer to {question}"),
    ]


def _reasoning(text="thinking"):
    return {
        "type": "reasoning",
        "summary": [{"type": "summary_text", "text": text}],
        "encrypted_content": "enc",
    }


class TestCurrentTurn:
    def test_current_turn_is_never_trimmed_even_over_budget(self):
        current = [
            HumanMessage(content="now"),
            AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "c1"}]),
            ToolMessage(content="huge " * 1000, tool_call_id="c1", name="t"),
        ]

        out = _build([*_tool_turn("old", "o1"), *current], budget=10)

        assert out[-len(current) :] == current

    def test_current_turn_keeps_its_reasoning_blocks_and_full_tool_results(self):
        ai = AIMessage(
            content=[_reasoning(), {"type": "text", "text": "looking"}],
            tool_calls=[{"name": "t", "args": {}, "id": "c1"}],
        )
        tool = ToolMessage(
            content="full figures", tool_call_id="c1", name="t", artifact={"title": "T", "period": None}
        )
        current = [HumanMessage(content="now"), ai, tool]

        out = _build(current)

        assert out[-3:] == current
        assert out[-2].content[0]["type"] == "reasoning"
        assert out[-1].content == "full figures"

    def test_a_history_without_a_human_message_is_all_current_turn(self):
        messages = [AIMessage(content="hello")]

        assert _build(messages, budget=0)[-1:] == messages


class TestEarlierTurns:
    def test_earlier_tool_results_become_stubs(self):
        original = _tool_turn("old", "o1")[2]

        out = _build([*_tool_turn("old", "o1"), HumanMessage(content="now")])

        stub = next(m for m in out if isinstance(m, ToolMessage))
        assert (
            stub.content
            == "Spending by category · Sep 2026: result omitted from an earlier turn; call the tool again for figures."
        )
        assert stub.tool_call_id == original.tool_call_id
        assert stub.content == STUB_TEMPLATE.format(title="Spending by category", period=" · Sep 2026")

    def test_stub_without_a_period_has_none(self):
        history = _tool_turn("old", "o1", title="Net worth", period=None)

        stub = next(m for m in _build([*history, HumanMessage(content="now")]) if isinstance(m, ToolMessage))

        assert stub.content.startswith("Net worth: result omitted")

    def test_error_result_without_artifact_is_stubbed_by_the_tool_name(self):
        history = [
            HumanMessage(content="old"),
            AIMessage(content="", tool_calls=[{"name": "search_transactions", "args": {}, "id": "o1"}]),
            ToolMessage(content="The tool failed", tool_call_id="o1", name="search_transactions", status="error"),
            AIMessage(content="sorry"),
        ]

        stub = next(m for m in _build([*history, HumanMessage(content="now")]) if isinstance(m, ToolMessage))

        assert stub.content == STUB_TEMPLATE.format(title="search_transactions", period="")

    def test_error_result_with_no_known_name_is_stubbed_as_tool(self):
        history = [
            HumanMessage(content="old"),
            AIMessage(content="", tool_calls=[{"name": "", "args": {}, "id": "o1"}]),
            ToolMessage(content="nope", tool_call_id="o1", status="error"),
        ]

        stub = next(m for m in _build([*history, HumanMessage(content="now")]) if isinstance(m, ToolMessage))

        assert stub.content.startswith("Tool: result omitted")

    def test_reasoning_blocks_are_stripped_from_earlier_turns(self):
        history = [
            HumanMessage(content="old"),
            AIMessage(content=[_reasoning(), {"type": "text", "text": "the answer"}]),
        ]

        out = _build([*history, HumanMessage(content="now")])

        assert out[2].content == "the answer"

    def test_an_earlier_tool_call_message_emptied_by_stripping_stays_with_its_pair(self):
        call = {"name": "category_breakdown", "args": {}, "id": "o1"}
        history = [
            HumanMessage(content="old"),
            AIMessage(content=[_reasoning()], tool_calls=[call]),
            ToolMessage(
                content="r", tool_call_id="o1", name="category_breakdown", artifact={"title": "T", "period": None}
            ),
            AIMessage(content="done"),
        ]

        out = _build([*history, HumanMessage(content="now")])

        ai = out[2]
        assert isinstance(ai, AIMessage) and ai.content == "" and ai.tool_calls[0]["id"] == "o1"
        assert isinstance(out[3], ToolMessage) and out[3].tool_call_id == "o1"

    def test_oldest_turns_drop_first_and_tool_pairs_stay_whole(self):
        history = [*_tool_turn("first", "a"), *_tool_turn("second", "b"), *_tool_turn("third", "c")]
        current = [HumanMessage(content="now")]
        full = _build([*history, *current])
        one_turn = len(_build([*_tool_turn("third", "c"), *current]))
        # Budget that fits the prompt, the newest turn, and nothing older.
        budget = _chars(_build([*_tool_turn("third", "c"), *current]))

        out = _build([*history, *current], budget=budget)

        assert len(out) == one_turn < len(full)
        assert [m.text for m in out if isinstance(m, HumanMessage)] == ["third", "now"]
        call_ids = {c["id"] for m in out if isinstance(m, AIMessage) for c in m.tool_calls}
        assert {m.tool_call_id for m in out if isinstance(m, ToolMessage)} <= call_ids

    def test_a_tool_call_without_a_result_is_not_sent(self):
        history = [
            HumanMessage(content="old"),
            AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "lost"}]),
        ]

        out = _build([*history, HumanMessage(content="now")])

        assert not any(isinstance(m, AIMessage) and m.tool_calls for m in out)


class TestLayout:
    def test_static_prompt_comes_first_and_turn_context_after_history(self):
        current = [HumanMessage(content="now")]
        out = build_model_context(
            [*_tool_turn("old", "o1"), *current],
            system_prompt=load_system_prompt(),
            turn_context_text=TURN_CONTEXT,
            budget_tokens=10_000,
            count_tokens=_chars,
        )

        assert out[0].content == load_system_prompt() and isinstance(out[0], SystemMessage)
        assert isinstance(out[-len(current) - 1], SystemMessage)
        assert out[-len(current) - 1].content == TURN_CONTEXT
        assert out[-1] == current[0]

    def test_a_real_registry_llm_token_counter_works_through_the_fallback_wrapper(self):
        llm = LLMRegistry.get(LLMRegistry.get_all_names()[0])

        out = build_model_context(
            [HumanMessage(content="hello")],
            system_prompt="be helpful",
            turn_context_text=TURN_CONTEXT,
            budget_tokens=10_000,
            count_tokens=with_estimate_fallback(llm.get_num_tokens_from_messages),
        )

        assert [m.content for m in out] == ["be helpful", TURN_CONTEXT, "hello"]


class TestEstimate:
    def test_counts_text_and_reasoning_summary_text(self):
        plain = estimate_tokens([AIMessage(content="a" * 400)])
        with_reasoning = estimate_tokens(
            [AIMessage(content=[_reasoning("r" * 400), {"type": "text", "text": "a" * 400}])]
        )

        assert plain == 101
        assert with_reasoning == 201

    def test_counter_that_raises_falls_back_to_the_estimate(self):
        def broken(_messages):
            raise ValueError("Unrecognized content block type reasoning")

        messages = [HumanMessage(content="a" * 400)]

        assert with_estimate_fallback(broken)(messages) == estimate_tokens(messages)

    def test_fallback_still_trims_an_unmeasurable_history(self):
        def broken(_messages):
            raise ValueError("boom")

        history = [*_tool_turn("old", "o1", result="x" * 4000), HumanMessage(content="now")]

        out = _build(history, budget=5, count=with_estimate_fallback(broken))

        assert [m.text for m in out] == [PROMPT, TURN_CONTEXT, "now"]


class TestPrompts:
    def test_system_prompt_has_no_date_or_memory_placeholders(self):
        assert "{" not in load_system_prompt()

    def test_system_prompt_states_the_finance_rules(self):
        prompt = load_system_prompt().lower()

        for phrase in ("this turn", "savings & investments", "category_breakdown", "csv", "read-only", "€"):
            assert phrase in prompt

    def test_turn_context_carries_date_preamble_and_memory(self):
        text = render_turn_context(
            today=dt.date(2026, 10, 20), memory="Saving for a flat", preamble="Last month: Sep 2026"
        )

        assert "2026-10-20" in text and "Last month: Sep 2026" in text and "Saving for a flat" in text

    def test_turn_context_without_preamble_or_memory_still_has_the_date(self):
        text = render_turn_context(today=dt.date(2026, 10, 20), memory="", preamble="")

        assert "2026-10-20" in text
