"""Tests for app.agents.chatbot.middleware.summary — folding earlier turns into a running summary."""

from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableLambda

from app.agents.chatbot.middleware.request_shaping import STUB_TEMPLATE
from app.agents.chatbot.middleware.summary import SummaryMiddleware, render_for_summary
from app.agents.chatbot.prompts import load_summary_prompt
from app.core.config import settings

pytestmark = pytest.mark.unit

MODULE = "app.agents.chatbot.middleware.summary"
SUMMARY = "Earlier the user asked about groceries."


def _turn(question: str, key: str, *, result: str = "x"):
    return [
        HumanMessage(content=question, id=f"h-{key}"),
        AIMessage(content="", tool_calls=[{"name": "category_breakdown", "args": {}, "id": key}], id=f"c-{key}"),
        ToolMessage(
            content=result,
            tool_call_id=key,
            name="category_breakdown",
            artifact={"title": "Spending by category", "period": "Sep 2026"},
            id=f"t-{key}",
        ),
        AIMessage(content=f"answer to {question}", id=f"a-{key}"),
    ]


class _Model:
    """A summary model that records its input."""

    def __init__(self, fail: bool = False):
        self.seen: list = []

        def call(messages):
            self.seen.append(messages)
            if fail:
                raise RuntimeError("boom")
            return AIMessage(SUMMARY)

        self.runnable = RunnableLambda(call)

    @property
    def human_text(self) -> str:
        return self.seen[0][1].text


async def _run(messages, *, state=None, model=None, budget=1, monkeypatch):
    monkeypatch.setattr(settings.llm, "CHAT_HISTORY_MAX_TOKENS", budget)
    model = model or _Model()
    with patch(f"{MODULE}.get_config", return_value={"configurable": {"thread_id": "thread-1"}}):
        update = await SummaryMiddleware(model=model.runnable).abefore_model(
            {"messages": messages, **(state or {})}, runtime=None
        )
    return update, model


async def test_under_budget_does_nothing(monkeypatch):
    update, model = await _run(
        [*_turn("groceries?", "a"), HumanMessage(content="now")], budget=100_000, monkeypatch=monkeypatch
    )

    assert update is None and model.seen == []


async def test_over_budget_folds_every_earlier_turn_and_sets_the_cutoff(monkeypatch):
    first, second = _turn("groceries?", "a"), _turn("rent?", "b")

    update, model = await _run([*first, *second, HumanMessage(content="now")], monkeypatch=monkeypatch)

    assert update == {"summary": SUMMARY, "summary_through": "a-b"}
    assert isinstance(model.seen[0][0], SystemMessage) and model.seen[0][0].text == load_summary_prompt()
    assert "groceries?" in model.human_text and "rent?" in model.human_text
    assert "now" not in model.human_text


async def test_only_turns_after_the_cutoff_are_folded(monkeypatch):
    first, second = _turn("groceries?", "a"), _turn("rent?", "b")

    update, model = await _run(
        [*first, *second, HumanMessage(content="now")],
        state={"summary": "old", "summary_through": "a-a"},
        monkeypatch=monkeypatch,
    )

    assert update["summary_through"] == "a-b"
    assert "groceries?" not in model.human_text and "rent?" in model.human_text


async def test_the_summariser_reads_stubbed_turns_not_raw_tool_results(monkeypatch):
    messages = [*_turn("spend?", "a", result="Groceries 180.50 EUR"), HumanMessage(content="now")]

    _, model = await _run(messages, monkeypatch=monkeypatch)

    assert "180.50" not in model.human_text
    assert STUB_TEMPLATE.format(title="Spending by category", period=" · Sep 2026") in model.human_text


async def test_the_existing_summary_is_folded_in(monkeypatch):
    _, model = await _run(
        [*_turn("rent?", "a"), HumanMessage(content="now")],
        state={"summary": "The user is saving for a flat."},
        monkeypatch=monkeypatch,
    )

    assert "Summary so far:\nThe user is saving for a flat." in model.human_text


async def test_no_summary_yet_reads_none(monkeypatch):
    _, model = await _run([*_turn("rent?", "a"), HumanMessage(content="now")], monkeypatch=monkeypatch)

    assert "Summary so far:\n(none)" in model.human_text


async def test_a_failed_summary_call_is_logged_and_the_turn_proceeds(monkeypatch):
    with patch(f"{MODULE}.logger") as log:
        update, _ = await _run(
            [*_turn("rent?", "a"), HumanMessage(content="now")], model=_Model(fail=True), monkeypatch=monkeypatch
        )

    assert update is None
    assert log.exception.call_args.args[0] == "chat_summary_failed"
    assert log.exception.call_args.kwargs["thread_id"] == "thread-1"


async def test_a_failure_to_read_the_thread_id_does_not_mask_the_failure(monkeypatch):
    monkeypatch.setattr(settings.llm, "CHAT_HISTORY_MAX_TOKENS", 1)
    middleware = SummaryMiddleware(model=_Model(fail=True).runnable)

    with patch(f"{MODULE}.get_config", side_effect=RuntimeError("no config")), patch(f"{MODULE}.logger") as log:
        update = await middleware.abefore_model(
            {"messages": [*_turn("rent?", "a"), HumanMessage(content="now")]}, runtime=None
        )

    assert update is None
    assert log.exception.call_args.kwargs["thread_id"] is None


def test_constructing_the_middleware_builds_no_client():
    with patch(f"{MODULE}.chat_model") as build:
        SummaryMiddleware()

    build.assert_not_called()


def test_render_for_summary_lines():
    turn = _turn("rent?", "a")
    shaped = [turn]

    text = render_for_summary(shaped)

    assert text.splitlines()[0] == "User: rent?"
    assert text.splitlines()[-1] == "Assistant: answer to rent?"
    assert "Tool result: " in text
    assert "Assistant: \n" not in text + "\n"  # a text-less tool-call message adds no line
