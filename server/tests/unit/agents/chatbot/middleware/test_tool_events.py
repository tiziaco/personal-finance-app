"""Tests for app.agents.chatbot.middleware.tool_events — events, metrics and error texts around a tool call."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool, ToolException
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from prometheus_client import REGISTRY
from pydantic import BaseModel, ConfigDict

from app.agents.chatbot.middleware.tool_events import (
    TOOL_ARGS_LOG_LIMIT,
    TOOL_FAILED_MESSAGE,
    TOOL_UNKNOWN_MESSAGE,
    ToolCallFinished,
    ToolCallStarted,
    ToolEventsMiddleware,
)

pytestmark = pytest.mark.unit

MODULE = "app.agents.chatbot.middleware.tool_events"
ARTIFACT = {"kind": "table"}


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: int


class TextArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


def _tool(name: str = "t", behaviour=None, args_schema: type[BaseModel] = Args) -> StructuredTool:
    async def run(**kwargs):
        if behaviour is not None:
            raise behaviour
        return f"got {kwargs}", ARTIFACT

    return StructuredTool.from_function(
        coroutine=run, name=name, description="d", args_schema=args_schema, response_format="content_and_artifact"
    )


def _request(tool, args: dict, call_id: str = "c1", name: str = "t"):
    events: list = []
    runtime = SimpleNamespace(stream_writer=events.append)
    call = {"name": name, "args": args, "id": call_id, "type": "tool_call"}
    return ToolCallRequest(tool_call=call, tool=tool, state={}, runtime=runtime), events


def _ok_handler(request):
    async def handler(req):
        return ToolMessage(
            content="fine", name=req.tool_call["name"], tool_call_id=req.tool_call["id"], artifact=ARTIFACT
        )

    return handler


def _raising(error: Exception):
    async def handler(req):
        raise error

    return handler


def _count(tool: str, outcome: str) -> int:
    return int(REGISTRY.get_sample_value("tool_calls_total", {"tool": tool, "outcome": outcome}) or 0)


def _observed(tool: str) -> int:
    return int(REGISTRY.get_sample_value("tool_call_duration_seconds_count", {"tool": tool}) or 0)


async def test_success_carries_the_artifact_and_emits_started_then_finished():
    request, events = _request(_tool("t_ok"), {"n": 1}, name="t_ok")
    before = _count("t_ok", "success")

    message = await ToolEventsMiddleware().awrap_tool_call(request, _ok_handler(request))

    assert message.content == "fine" and message.artifact == ARTIFACT and message.status == "success"
    assert events == [ToolCallStarted(id="c1", name="t_ok"), ToolCallFinished(id="c1", ok=True, artifact=ARTIFACT)]
    assert _count("t_ok", "success") == before + 1


async def test_invalid_arguments_return_the_validation_message_and_count_invalid_args():
    request, events = _request(_tool("t_bad"), {"n": "x"}, name="t_bad")
    before = _count("t_bad", "invalid_args")

    async def handler(req):
        raise AssertionError("the tool must not run")

    message = await ToolEventsMiddleware().awrap_tool_call(request, handler)

    assert message.status == "error"
    assert message.content.startswith("Invalid arguments: n: Input should be a valid integer")
    assert events[-1] == ToolCallFinished(id="c1", ok=False, artifact=None)
    assert _count("t_bad", "invalid_args") == before + 1


async def test_unknown_argument_names_are_rejected_in_the_same_wording():
    request, _ = _request(_tool("t_extra"), {"n": 1, "z": 2}, name="t_extra")

    message = await ToolEventsMiddleware().awrap_tool_call(request, _ok_handler(request))

    assert message.content.startswith("Invalid arguments: z: Extra inputs are not permitted")


async def test_tool_exception_text_reaches_the_model_as_invalid_args():
    request, events = _request(_tool("t_exc"), {"n": 1}, name="t_exc")
    before = _count("t_exc", "invalid_args")

    message = await ToolEventsMiddleware().awrap_tool_call(request, _raising(ToolException("category must be x")))

    assert message.status == "error" and message.content == "category must be x"
    assert events[-1] == ToolCallFinished(id="c1", ok=False, artifact=None)
    assert _count("t_exc", "invalid_args") == before + 1


async def test_a_crash_returns_the_fixed_message_and_counts_error():
    request, events = _request(_tool("t_crash"), {"n": 1}, name="t_crash")
    before = _count("t_crash", "error")

    with patch(f"{MODULE}.logger") as log:
        message = await ToolEventsMiddleware().awrap_tool_call(request, _raising(RuntimeError("secret upstream")))

    assert message.status == "error" and message.content == TOOL_FAILED_MESSAGE
    assert "secret" not in message.content
    assert events[-1] == ToolCallFinished(id="c1", ok=False, artifact=None)
    assert _count("t_crash", "error") == before + 1
    assert log.exception.call_args.args[0] == "tool_call_failed"


async def test_an_unknown_tool_returns_the_fixed_text_without_events_and_counts_unknown_tool():
    request, events = _request(None, {"n": 1}, name="made_up")
    before = _count("made_up", "unknown_tool")

    with patch(f"{MODULE}.logger") as log:
        message = await ToolEventsMiddleware().awrap_tool_call(request, _ok_handler(request))

    assert message.status == "error" and message.content == TOOL_UNKNOWN_MESSAGE
    assert message.tool_call_id == "c1" and message.name == "made_up"
    assert events == []
    assert _count("made_up", "unknown_tool") == before + 1
    assert log.error.call_args.args[0] == "tool_call_unknown_tool"
    assert "known_tools" not in log.error.call_args.kwargs


@pytest.mark.parametrize(
    ("name", "args", "handler"),
    [
        ("d_ok", {"n": 1}, None),
        ("d_bad", {"n": "x"}, None),
        ("d_exc", {"n": 1}, ToolException("no")),
        ("d_crash", {"n": 1}, RuntimeError("boom")),
    ],
)
async def test_duration_is_observed_on_every_outcome(name, args, handler):
    request, _ = _request(_tool(name), args, name=name)
    before = _observed(name)

    await ToolEventsMiddleware().awrap_tool_call(request, _raising(handler) if handler else _ok_handler(request))

    assert _observed(name) == before + 1


async def test_long_args_are_truncated_in_the_log():
    request, _ = _request(_tool("t_long", args_schema=TextArgs), {"text": "x" * 1000}, name="t_long")

    with patch(f"{MODULE}.logger") as log:
        await ToolEventsMiddleware().awrap_tool_call(request, _ok_handler(request))

    logged = log.debug.call_args.kwargs["tool_args"]
    assert logged.endswith("...") and len(logged) == TOOL_ARGS_LOG_LIMIT + 3
    assert log.info.call_args.kwargs["result_chars"] == len("fine")


async def test_one_valid_and_one_invalid_call_both_report():
    middleware = ToolEventsMiddleware()
    tool = _tool("t_two")
    good, good_events = _request(tool, {"n": 1}, call_id="a", name="t_two")
    bad, bad_events = _request(tool, {"n": "x"}, call_id="b", name="t_two")
    ok_before, bad_before = _count("t_two", "success"), _count("t_two", "invalid_args")

    first = await middleware.awrap_tool_call(good, _ok_handler(good))
    second = await middleware.awrap_tool_call(bad, _ok_handler(bad))

    assert [first.tool_call_id, second.tool_call_id] == ["a", "b"]
    assert [type(e) for e in good_events + bad_events] == [ToolCallStarted, ToolCallFinished] * 2
    assert _count("t_two", "success") == ok_before + 1
    assert _count("t_two", "invalid_args") == bad_before + 1


# The library's ToolNode is what runs the hook in the agent; these run a real one.


def _graph(tool: StructuredTool):
    node = ToolNode([tool], awrap_tool_call=ToolEventsMiddleware().awrap_tool_call)
    return StateGraph(MessagesState).add_node("tools", node).add_edge(START, "tools").add_edge("tools", END).compile()


async def _run_real(tool: StructuredTool, calls: list[dict]):
    ai = AIMessage(content="", tool_calls=[{**c, "type": "tool_call"} for c in calls])
    events: list = []
    result = None
    async for mode, chunk in _graph(tool).astream(
        {"messages": [HumanMessage(content="q"), ai]}, stream_mode=["custom", "values"]
    ):
        if mode == "custom":
            events.append(chunk)
        else:
            result = chunk
    return result["messages"][2:], events


async def test_a_real_tool_node_lets_a_tool_exception_reach_the_hook():
    tool = _tool("r_exc", behaviour=ToolException("category must be x"))
    before = _count("r_exc", "invalid_args")

    messages, events = await _run_real(tool, [{"name": "r_exc", "args": {"n": 1}, "id": "c1"}])

    assert [(m.content, m.status) for m in messages] == [("category must be x", "error")]
    assert events == [ToolCallStarted(id="c1", name="r_exc"), ToolCallFinished(id="c1", ok=False, artifact=None)]
    assert _count("r_exc", "invalid_args") == before + 1


async def test_a_real_tool_node_lets_a_crash_reach_the_hook_and_the_model_sees_the_fixed_text():
    tool = _tool("r_crash", behaviour=RuntimeError("secret"))
    before = _count("r_crash", "error")

    messages, _ = await _run_real(tool, [{"name": "r_crash", "args": {"n": 1}, "id": "c1"}])

    assert [(m.content, m.status) for m in messages] == [(TOOL_FAILED_MESSAGE, "error")]
    assert _count("r_crash", "error") == before + 1


async def test_a_real_tool_node_runs_success_invalid_and_unknown_calls_in_order():
    tool = _tool("r_mix")
    calls = [
        {"name": "r_mix", "args": {"n": 1}, "id": "a"},
        {"name": "r_mix", "args": {"n": "x"}, "id": "b"},
        {"name": "r_nope", "args": {}, "id": "c"},
    ]

    messages, events = await _run_real(tool, calls)

    assert [m.tool_call_id for m in messages] == ["a", "b", "c"]
    assert messages[0].artifact == ARTIFACT and messages[0].status == "success"
    assert messages[1].content.startswith("Invalid arguments: n:")
    assert messages[2].content == TOOL_UNKNOWN_MESSAGE
    assert sorted(type(e).__name__ for e in events) == ["ToolCallFinished"] * 2 + ["ToolCallStarted"] * 2
    assert json.dumps(messages[0].artifact)


async def test_a_real_tool_node_error_message_from_a_validation_error_in_the_body_is_a_crash():
    try:
        Args(n="x")  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001
        body_error = exc
    tool = _tool("r_val", behaviour=body_error)
    before = _count("r_val", "error")

    with patch(f"{MODULE}.logger") as log:
        messages, events = await _run_real(tool, [{"name": "r_val", "args": {"n": 1}, "id": "c1"}])

    assert [(m.content, m.status) for m in messages] == [(TOOL_FAILED_MESSAGE, "error")]
    assert events[-1] == ToolCallFinished(id="c1", ok=False, artifact=None)
    assert _count("r_val", "error") == before + 1
    assert log.error.call_args.args[0] == "tool_call_failed"


async def test_a_command_from_the_handler_passes_through():
    from langgraph.types import Command

    request, events = _request(_tool("t_cmd"), {"n": 1}, name="t_cmd")
    command = Command(update={})

    async def handler(req):
        return command

    assert await ToolEventsMiddleware().awrap_tool_call(request, handler) is command
    assert events[-1] == ToolCallFinished(id="c1", ok=True, artifact=None)
