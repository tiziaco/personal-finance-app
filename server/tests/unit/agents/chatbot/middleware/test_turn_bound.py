"""Tests for app.agents.chatbot.middleware.turn_bound — the step cap, repeat detection and the wrap-up call."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langchain.agents.middleware import ExtendedModelResponse, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agents.chatbot.context import TurnContext
from app.agents.chatbot.middleware.turn_bound import (
    STOPPED_FALLBACK_TEXT,
    WRAP_UP_INSTRUCTION,
    TurnBoundMiddleware,
    repeated_call,
    turn_steps,
)
from app.core.config import settings

pytestmark = pytest.mark.unit

MODULE = "app.agents.chatbot.middleware.turn_bound"


def _call(name: str, n: int, call_id: str) -> dict:
    return {"name": name, "args": {"n": n}, "id": call_id}


def _tool_calling(n: int = 1, call_id: str = "new") -> AIMessage:
    return AIMessage(content="", tool_calls=[_call("t", n, call_id)])


def _earlier_steps(count: int, *, n=None) -> list:
    """A current turn that has already made `count` tool-calling steps (distinct arguments unless `n` is given)."""
    messages: list = [HumanMessage(content="q")]
    for i in range(count):
        call = _call("t", i if n is None else n, f"c{i}")
        messages += [AIMessage(content="", tool_calls=[call]), ToolMessage(content="r", tool_call_id=f"c{i}")]
    return messages


async def _run(messages, replies, *, state_extra=None):
    """Run the middleware over `messages`; `replies` is a queue of AIMessages or exceptions for the handler.

    Returns (result, requests the handler saw).
    """
    queue = list(replies)
    seen: list[ModelRequest] = []

    async def handler(request):
        seen.append(request)
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return ModelResponse(result=[reply])

    request = ModelRequest(
        model=MagicMock(),
        messages=messages,
        system_message=SystemMessage("sys"),
        tool_choice=None,
        tools=[MagicMock()],
        response_format=None,
        state={"messages": messages, **(state_extra or {})},
        runtime=SimpleNamespace(context=TurnContext(user_id=MagicMock(), session_factory=MagicMock())),
        model_settings={},
    )
    with patch(f"{MODULE}.get_config", return_value={"configurable": {"thread_id": "thread-1"}}):
        result = await TurnBoundMiddleware().awrap_model_call(request, handler)
    return result, seen


def _final(result: ExtendedModelResponse) -> AIMessage:
    return result.model_response.result[0]


async def test_every_call_up_to_the_cap_is_made_with_tools_and_goes_on_to_the_tools(monkeypatch):
    monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 2)
    reply = _tool_calling()

    result, seen = await _run([HumanMessage(content="q")], [reply])

    assert isinstance(result, ModelResponse) and result.result == [reply]
    assert len(seen) == 1 and seen[0].tools


async def test_the_capth_tool_calling_response_is_dropped_and_a_tool_less_wrap_up_answers(monkeypatch):
    monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 2)
    messages = _earlier_steps(1)

    result, seen = await _run(messages, [_tool_calling(5), AIMessage(content="Partial answer.")])

    final = _final(result)
    assert final.text == "Partial answer." and not final.tool_calls
    assert result.command.update == {"stopped": {final.id: "step_limit"}}
    assert len(seen) == 2
    assert seen[0].tools and seen[1].tools == []
    assert seen[1].messages == [*messages, SystemMessage(WRAP_UP_INSTRUCTION)]
    assert result.model_response.result == [final]


async def test_a_text_answer_on_the_last_allowed_call_ends_the_turn_unstopped(monkeypatch):
    monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 2)
    reply = AIMessage(content="Done.")

    result, seen = await _run(_earlier_steps(1), [reply])

    assert isinstance(result, ModelResponse) and result.result == [reply]
    assert len(seen) == 1


async def test_a_repeated_call_stops_the_loop_with_its_reason():
    messages = _earlier_steps(1, n=7)

    result, seen = await _run(messages, [_tool_calling(7), AIMessage(content="Partial answer.")])

    final = _final(result)
    assert result.command.update == {"stopped": {final.id: "repeated_call"}}
    assert len(seen) == 2 and seen[1].tools == []


async def test_a_failing_wrap_up_falls_back_to_the_fixed_text(monkeypatch):
    monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 1)

    with patch(f"{MODULE}.logger") as log:
        result, _ = await _run([HumanMessage(content="q")], [_tool_calling(), RuntimeError("model down")])

    final = _final(result)
    assert final.content == STOPPED_FALLBACK_TEXT and final.id
    assert result.command.update == {"stopped": {final.id: "step_limit"}}
    assert log.exception.call_args.args[0] == "llm_wrap_up_failed"
    assert log.exception.call_args.kwargs["conversation_id"] == "thread-1"


async def test_an_empty_wrap_up_falls_back_to_the_fixed_text(monkeypatch):
    monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 1)

    result, _ = await _run([HumanMessage(content="q")], [_tool_calling(), AIMessage(content="  ")])

    assert _final(result).content == STOPPED_FALLBACK_TEXT


async def test_a_wrap_up_that_asks_for_tools_falls_back_to_the_fixed_text(monkeypatch):
    monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 1)
    wrap_up = AIMessage(content="Let me look.", tool_calls=[_call("t", 9, "x")])

    result, _ = await _run([HumanMessage(content="q")], [_tool_calling(), wrap_up])

    final = _final(result)
    assert final.content == STOPPED_FALLBACK_TEXT and not final.tool_calls
    assert result.command.update == {"stopped": {final.id: "step_limit"}}


async def test_an_empty_reply_fails_the_turn_and_is_logged_with_the_model():
    empty = AIMessage(content="", response_metadata={"model_name": "m-1", "status": "incomplete"})

    with patch(f"{MODULE}.logger") as log:
        with pytest.raises(Exception, match="empty reply"):
            await _run([HumanMessage(content="q")], [empty])

    assert log.warning.call_args.args[0] == "llm_empty_response"
    kwargs = log.warning.call_args.kwargs
    assert kwargs["model"] == "m-1" and kwargs["status"] == "incomplete" and kwargs["conversation_id"] == "thread-1"


async def test_stopped_keeps_earlier_entries(monkeypatch):
    monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 1)

    result, _ = await _run(
        [HumanMessage(content="q")],
        [_tool_calling(), AIMessage(content="Partial.")],
        state_extra={"stopped": {"old": "step_limit"}},
    )

    assert set(result.command.update["stopped"]) == {"old", _final(result).id}


def test_turn_steps_counts_only_this_turn():
    messages = [*_earlier_steps(3), AIMessage(content="done"), *_earlier_steps(2)]

    assert turn_steps(messages) == 2
    assert turn_steps([HumanMessage(content="q"), AIMessage(content="plain")]) == 0


def test_repeated_call_cases():
    same = [*_earlier_steps(1, n=1), _tool_calling(1)]
    different = [*_earlier_steps(1, n=1), AIMessage(content="", tool_calls=[_call("t", 2, "b"), _call("u", 1, "c")])]
    earlier_turn = [
        *_earlier_steps(1, n=1),
        AIMessage(content="done"),
        HumanMessage(content="again"),
        _tool_calling(1),
    ]

    assert repeated_call(same)
    assert not repeated_call(different)
    assert not repeated_call(earlier_turn)
