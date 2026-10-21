"""Tests for app.agents.chatbot.graph — the chat turn end to end on the real graph and middleware.

Each test compiles `build_chatbot` on a MemorySaver with a scripted model and the
test's own tools (`tests/unit/agents` imports no module's tools), and runs a turn.
"""

import asyncio
import datetime as dt
import uuid
from typing import Annotated, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import InjectedToolArg, StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field, SkipValidation

from app.agents.chatbot import ChatbotAgent, TurnContext, build_chatbot
from app.agents.chatbot.graph import turn_recursion_limit
from app.agents.chatbot.middleware.tool_events import (
    TOOL_FAILED_MESSAGE,
    TOOL_UNKNOWN_MESSAGE,
    ToolCallFinished,
    ToolCallStarted,
)
from app.agents.chatbot.middleware.turn_bound import STOPPED_FALLBACK_TEXT, WRAP_UP_INSTRUCTION
from app.agents.chatbot.prompts import load_system_prompt
from app.core.config import settings
from app.core.metadata import PROJECT_NAME
from tests.fakes.chat_model import ScriptedChatModel

pytestmark = pytest.mark.unit

USER_ID = uuid.uuid4()
DISPLAY = {"title": "T", "period": None, "summary": [{"kind": "count", "value": 1, "label": None}], "table": None}


class NArgs(BaseModel):
    """Shaped like the chat tools' `ToolArgs`: the model's field and the injected runtime slot."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    n: int
    runtime: Annotated[SkipValidation[Optional[ToolRuntime]], InjectedToolArg] = Field(None, exclude=True)


def make_tool(name: str = "t", run=None) -> StructuredTool:
    async def ok(runtime: ToolRuntime[TurnContext], n: int) -> tuple[str, dict]:
        return f"n is {n}", DISPLAY

    return StructuredTool.from_function(
        coroutine=run or ok,
        name=name,
        description=f"Does {name}.",
        args_schema=NArgs,
        response_format="content_and_artifact",
        metadata={"title": f"{name} title"},
    )


async def preamble(ctx: TurnContext) -> str:
    return "Last finished month: September 2026."


def context() -> TurnContext:
    return TurnContext(user_id=USER_ID, session_factory=MagicMock())


def config(thread: str = "t1", **extra) -> dict:
    return {"configurable": {"thread_id": thread}, **extra}


@pytest.fixture(autouse=True)
def no_memory():
    """mem0 is out of reach in a unit test: nothing relevant, and the write goes nowhere."""
    with (
        patch("app.agents.chatbot.middleware.memory.get_relevant_memory", AsyncMock(return_value="")),
        patch("app.agents.chatbot.middleware.memory.update_memory", AsyncMock()),
    ):
        yield


async def test_a_text_turn_is_persisted_and_streams_from_the_model_node():
    graph = build_chatbot(MemorySaver(), [make_tool()], preamble, model=ScriptedChatModel(responses=[AIMessage("hi")]))

    items = [
        item
        async for item in graph.astream(
            {"messages": [HumanMessage("hello")]},
            config=config(),
            context=context(),
            stream_mode=["messages", "custom"],
        )
    ]

    streamed = [(m, meta) for mode, (m, meta) in (i for i in items if i[0] == "messages") if isinstance(m, AIMessage)]
    assert [(m.text, meta["langgraph_node"]) for m, meta in streamed] == [("hi", "model")]
    state = await graph.aget_state(config())
    assert [(type(m), m.text) for m in state.values["messages"]] == [(HumanMessage, "hello"), (AIMessage, "hi")]


# ── Helpers ───────────────────────────────────────────────────────────────────


def call(n: int, call_id: str, name: str = "t") -> AIMessage:
    """A reply asking for one tool call."""
    return AIMessage("", tool_calls=[{"name": name, "args": {"n": n}, "id": call_id, "type": "tool_call"}])


def counting_tool() -> tuple[StructuredTool, list[int]]:
    """A tool that records each `n` it runs with."""
    ran: list[int] = []

    async def run(runtime: ToolRuntime[TurnContext], n: int) -> tuple[str, dict]:
        ran.append(n)
        return f"n is {n}", DISPLAY

    return make_tool(run=run), ran


def is_wrap_up(request: list) -> bool:
    return isinstance(request[-1], SystemMessage) and request[-1].content == WRAP_UP_INSTRUCTION


async def run_turn(graph, text: str = "q", thread: str = "t1", **extra) -> dict:
    return await graph.ainvoke({"messages": [HumanMessage(text)]}, config=config(thread, **extra), context=context())


async def stream_turn(graph, text: str = "q", thread: str = "t1") -> list[tuple[str, object]]:
    return [
        item
        async for item in graph.astream(
            {"messages": [HumanMessage(text)]},
            config=config(thread),
            context=context(),
            stream_mode=["messages", "custom"],
        )
    ]


# ── Turn limits ───────────────────────────────────────────────────────────────


async def test_step_cap_ends_the_turn_with_a_wrap_up_answer_marked_stopped(monkeypatch):
    monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 2)
    tool, ran = counting_tool()
    second = call(2, "c2")
    model = ScriptedChatModel(responses=[call(1, "c1"), second, AIMessage("Partial answer.")])

    state = await run_turn(build_chatbot(MemorySaver(), [tool], preamble, model=model))

    final = state["messages"][-1]
    assert final.text == "Partial answer." and not final.tool_calls
    assert state["stopped"] == {final.id: "step_limit"}
    assert ran == [1]
    assert [is_wrap_up(request) for request in model.sent] == [False, False, True]
    # The dropped tool-calling reply is never persisted, so it is never run either.
    assert not any(m.tool_calls == second.tool_calls for m in state["messages"] if isinstance(m, AIMessage))


async def test_a_long_cap_is_what_ends_the_turn_not_langgraphs_recursion_limit(monkeypatch):
    monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 12)
    tool, ran = counting_tool()
    model = ScriptedChatModel(responses=[*(call(n, f"c{n}") for n in range(1, 13)), AIMessage("Partial answer.")])
    limit = turn_recursion_limit(12)

    state = await run_turn(build_chatbot(MemorySaver(), [tool], preamble, model=model), recursion_limit=limit)

    assert state["stopped"] == {state["messages"][-1].id: "step_limit"}
    assert len(ran) == 11
    # A backstop, not a bound the cap could never reach: it sits just above the turn's supersteps.
    assert 3 * 12 <= limit < 3 * 12 + 10


async def test_at_the_default_cap_the_agents_own_config_ends_the_turn_with_the_wrap_up():
    """The limit the agent puts in its turn config, at the shipped `CHAT_MAX_STEPS`, lets the cap be met."""
    steps = settings.llm.CHAT_MAX_STEPS
    tool, ran = counting_tool()
    model = ScriptedChatModel(responses=[*(call(n, f"c{n}") for n in range(1, steps + 1)), AIMessage("Partial.")])
    agent = ChatbotAgent(build_chatbot(MemorySaver(), [tool], preamble, model=model), [tool])

    with patch("app.agents.core.observability.CallbackHandler"):
        messages, stopped = await agent.run("q", uuid.uuid4(), context())

    assert stopped == {messages[-1].id: "step_limit"}
    assert messages[-1].text == "Partial."
    assert len(ran) == steps - 1


async def test_repeated_identical_call_stops_the_loop():
    tool, ran = counting_tool()
    model = ScriptedChatModel(responses=[call(7, "c1"), call(7, "c2"), AIMessage("Partial answer.")])

    state = await run_turn(build_chatbot(MemorySaver(), [tool], preamble, model=model))

    assert state["stopped"] == {state["messages"][-1].id: "repeated_call"}
    assert ran == [7]
    assert [is_wrap_up(request) for request in model.sent] == [False, False, True]


async def test_a_failing_wrap_up_falls_back_to_the_fixed_text(monkeypatch):
    monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 1)
    tool, _ = counting_tool()
    model = ScriptedChatModel(responses=[call(1, "c1"), RuntimeError("model down")])

    state = await run_turn(build_chatbot(MemorySaver(), [tool], preamble, model=model))

    final = state["messages"][-1]
    assert final.content == STOPPED_FALLBACK_TEXT
    assert state["stopped"] == {final.id: "step_limit"}


async def test_the_step_count_starts_again_on_each_turn(monkeypatch):
    monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 2)
    tool, _ = counting_tool()
    model = ScriptedChatModel(responses=[call(1, "c1"), AIMessage("ok"), call(2, "c2"), AIMessage("ok")])
    graph = build_chatbot(MemorySaver(), [tool], preamble, model=model)

    await run_turn(graph)
    state = await run_turn(graph, text="again")

    assert not state.get("stopped")
    assert state["messages"][-1].text == "ok"


async def test_the_next_turn_works_after_a_stopped_one(monkeypatch):
    monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 1)
    tool, _ = counting_tool()
    model = ScriptedChatModel(responses=[call(1, "c1"), AIMessage("Partial."), AIMessage("Fine.")])
    graph = build_chatbot(MemorySaver(), [tool], preamble, model=model)

    await run_turn(graph)
    state = await run_turn(graph, text="next")

    assert not any(isinstance(m, AIMessage) and m.tool_calls for m in model.sent[-1])
    assert state["messages"][-1].text == "Fine."


# ── Tool calls ────────────────────────────────────────────────────────────────


async def test_tool_calls_run_concurrently_and_one_crash_does_not_sink_the_other():
    started = {"a": asyncio.Event(), "b": asyncio.Event()}

    def waiting(name: str) -> StructuredTool:
        async def run(runtime: ToolRuntime[TurnContext], n: int) -> tuple[str, dict]:
            started[name].set()
            # Completes only if the other call has started too: sequential execution would hang.
            await asyncio.wait_for(asyncio.gather(*(e.wait() for e in started.values())), timeout=2)
            return f"n is {n}", DISPLAY

        return make_tool(name, run)

    async def crashes(runtime: ToolRuntime[TurnContext], n: int) -> tuple[str, dict]:
        await asyncio.wait_for(started["a"].wait(), timeout=2)
        raise RuntimeError("boom")

    calls = [{"name": name, "args": {"n": i}, "id": f"c{i}", "type": "tool_call"} for i, name in enumerate("abc")]
    model = ScriptedChatModel(responses=[AIMessage("", tool_calls=calls), AIMessage("Done.")])
    graph = build_chatbot(MemorySaver(), [waiting("a"), waiting("b"), make_tool("c", crashes)], preamble, model=model)

    state = await run_turn(graph)

    results = [m for m in state["messages"] if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in results] == ["c0", "c1", "c2"]
    assert [m.status for m in results] == ["success", "success", "error"]
    assert results[2].content == TOOL_FAILED_MESSAGE
    assert state["messages"][-1].text == "Done."


async def test_the_custom_stream_carries_started_and_finished_for_each_call():
    async def crashes(runtime: ToolRuntime[TurnContext], n: int) -> tuple[str, dict]:
        raise RuntimeError("boom")

    calls = [
        {"name": "good", "args": {"n": 0}, "id": "c0", "type": "tool_call"},
        {"name": "bad", "args": {"n": 1}, "id": "c1", "type": "tool_call"},
    ]
    model = ScriptedChatModel(responses=[AIMessage("", tool_calls=calls), AIMessage("Done.")])
    graph = build_chatbot(MemorySaver(), [make_tool("good"), make_tool("bad", crashes)], preamble, model=model)

    events = [payload for mode, payload in await stream_turn(graph) if mode == "custom"]

    assert sorted(events, key=repr) == sorted(
        [
            ToolCallStarted(id="c0", name="good"),
            ToolCallFinished(id="c0", ok=True, artifact=DISPLAY),
            ToolCallStarted(id="c1", name="bad"),
            ToolCallFinished(id="c1", ok=False, artifact=None),
        ],
        key=repr,
    )
    assert events.index(ToolCallStarted(id="c0", name="good")) < events.index(
        ToolCallFinished(id="c0", ok=True, artifact=DISPLAY)
    )


async def test_an_unknown_tool_gets_the_fixed_text_and_no_event():
    model = ScriptedChatModel(responses=[call(1, "c1", name="invented"), AIMessage("OK.")])
    graph = build_chatbot(MemorySaver(), [make_tool()], preamble, model=model)

    items = await stream_turn(graph)

    assert not [payload for mode, payload in items if mode == "custom"]
    [result] = [m for m in (await graph.aget_state(config())).values["messages"] if isinstance(m, ToolMessage)]
    assert result.status == "error" and result.content == TOOL_UNKNOWN_MESSAGE


async def test_a_tool_reads_the_user_from_the_turn_context():
    seen = []

    async def run(runtime: ToolRuntime[TurnContext], n: int) -> tuple[str, dict]:
        seen.append(runtime.context.user_id)
        return "ok", DISPLAY

    model = ScriptedChatModel(responses=[call(1, "c1"), AIMessage("Done.")])
    await run_turn(build_chatbot(MemorySaver(), [make_tool(run=run)], preamble, model=model))

    assert seen == [USER_ID]


# ── What the model is sent ────────────────────────────────────────────────────


async def test_the_request_carries_the_system_prompt_then_turn_context_then_the_question():
    model = ScriptedChatModel(responses=[AIMessage("Sure.")])
    graph = build_chatbot(MemorySaver(), [make_tool()], preamble, model=model)

    with patch(
        "app.agents.chatbot.middleware.memory.get_relevant_memory", AsyncMock(return_value="Saving for a flat")
    ):
        await run_turn(graph, text="hi")

    [system, turn_context, question] = model.sent[0]
    assert system == SystemMessage(load_system_prompt())
    assert "Saving for a flat" not in system.content
    assert isinstance(turn_context, SystemMessage)
    assert f"Today's date: {dt.date.today().isoformat()}." in turn_context.content
    assert "Last finished month: September 2026." in turn_context.content
    assert "Saving for a flat" in turn_context.content
    assert question == HumanMessage("hi", id=question.id)


async def test_a_tool_call_left_without_a_result_is_not_sent():
    """Stop during a tool call, then send again: the next call must not 400."""
    model = ScriptedChatModel(responses=[AIMessage("Sure.")])
    graph = build_chatbot(MemorySaver(), [make_tool()], preamble, model=model)
    await graph.aupdate_state(config(), {"messages": [HumanMessage("What did I spend on rent"), call(1, "call_1")]})

    await run_turn(graph, text="Never mind, thanks")

    sent = model.sent[0]
    assert not any(getattr(m, "tool_calls", None) for m in sent)
    assert not any(isinstance(m, ToolMessage) for m in sent)
    # [static prompt, earlier turn..., turn context, current turn]
    assert [m.content for m in sent[1:-2]] == ["What did I spend on rent"]
    assert sent[-1].content == "Never mind, thanks"


async def test_a_failed_preamble_still_answers_the_turn():
    """The history load behind the preamble fails: the turn goes on without it, as a crashed tool would."""

    async def failing_preamble(ctx: TurnContext) -> str:
        raise RuntimeError("history load failed")

    model = ScriptedChatModel(responses=[AIMessage("Hello.")])
    graph = build_chatbot(MemorySaver(), [make_tool()], failing_preamble, model=model)

    with patch("app.agents.chatbot.middleware.request_shaping.logger") as log:
        state = await run_turn(graph, text="hi", thread="thread-9")

    assert state["messages"][-1].text == "Hello."
    [_, turn_context, question] = model.sent[0]
    assert f"Today's date: {dt.date.today().isoformat()}." in turn_context.content
    assert question.content == "hi"
    assert log.exception.call_args.args[0] == "chat_preamble_failed"
    assert log.exception.call_args.kwargs["thread_id"] == "thread-9"


class _PreCutoverState(BaseModel):
    """The channels the old hand-rolled loop checkpointed: no summary keys, a `turn_steps` count."""

    messages: Annotated[list, add_messages] = Field(default_factory=list)
    long_term_memory: str = ""
    turn_steps: int = 0
    stopped: dict[str, str] = Field(default_factory=dict)


async def test_a_thread_checkpointed_before_this_step_still_answers():
    """Review Focus 1: a checkpoint without `summary`/`summary_through` and with a stale `turn_steps`."""
    saver = MemorySaver()
    builder = StateGraph(_PreCutoverState)
    builder.add_node("chat", lambda state: {})
    builder.add_edge(START, "chat")
    old = builder.compile(checkpointer=saver)
    await old.aupdate_state(
        config(),
        {"messages": [HumanMessage("old question"), AIMessage("old answer")], "turn_steps": 5},
        as_node="chat",
    )
    model = ScriptedChatModel(responses=[AIMessage("New answer.")])

    state = await run_turn(build_chatbot(saver, [make_tool()], preamble, model=model), text="new question")

    assert [m.text for m in state["messages"]] == ["old question", "old answer", "new question", "New answer."]
    assert not state.get("stopped")
    # No summary yet, so the earlier turn goes as itself and no summary message is sent.
    assert [m.content for m in model.sent[0][1:3]] == ["old question", "old answer"]
    assert not any("Earlier in this conversation" in str(m.content) for m in model.sent[0])


@pytest.mark.parametrize(
    "reply",
    [
        AIMessage(content=""),
        AIMessage(content="  "),
        AIMessage(
            content=[],
            response_metadata={"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}},
        ),
    ],
)
async def test_the_empty_reply_fails_the_turn_and_nothing_empty_is_checkpointed(reply):
    graph = build_chatbot(MemorySaver(), [make_tool()], preamble, model=ScriptedChatModel(responses=[reply]))

    with pytest.raises(Exception, match="empty"):
        await run_turn(graph)

    messages = (await graph.aget_state(config())).values["messages"]
    assert [type(m) for m in messages] == [HumanMessage]


# ── Building the graph ────────────────────────────────────────────────────────


def test_an_empty_tools_list_fails_startup():
    with pytest.raises(ValueError, match="at least one tool"):
        build_chatbot(MemorySaver(), [], preamble, model=ScriptedChatModel(responses=[]))


def test_the_graph_is_named_for_the_project_and_environment():
    graph = build_chatbot(MemorySaver(), [make_tool()], preamble, model=ScriptedChatModel(responses=[]))

    assert graph.name == f"{PROJECT_NAME} Agent ({settings.ENVIRONMENT.value})"


def test_the_shipped_model_is_the_chats_primary_with_its_fallbacks_behind_the_timing():
    primary, fallback = ScriptedChatModel(responses=[]), ScriptedChatModel(responses=[])
    with (
        patch("app.agents.chatbot.graph.chat_model", return_value=primary) as build,
        patch("app.agents.chatbot.graph.fallback_models", return_value=[fallback]) as fallbacks,
        patch("app.agents.chatbot.graph.create_agent") as create,
    ):
        build_chatbot(MemorySaver(), [make_tool()], preamble)

    tuning = {"max_tokens": settings.llm.CHAT_REPLY_MAX_TOKENS, "reasoning_effort": settings.llm.CHAT_REASONING_EFFORT}
    build.assert_called_once_with(**tuning)
    fallbacks.assert_called_once_with(**tuning)
    assert create.call_args.args[0] is primary
    names = [type(m).__name__ for m in create.call_args.kwargs["middleware"]]
    assert names == [
        "MemoryMiddleware",
        "SummaryMiddleware",
        "TurnBoundMiddleware",
        "RequestShapingMiddleware",
        "ModelTimingMiddleware",
        "ModelFallbackMiddleware",
        "ToolEventsMiddleware",
    ]
    [fallback_middleware] = [
        m for m in create.call_args.kwargs["middleware"] if isinstance(m, ModelFallbackMiddleware)
    ]
    assert fallback_middleware.models == [fallback]


def test_no_fallback_models_means_no_fallback_middleware():
    with (
        patch("app.agents.chatbot.graph.chat_model"),
        patch("app.agents.chatbot.graph.fallback_models", return_value=[]),
        patch("app.agents.chatbot.graph.create_agent") as create,
    ):
        build_chatbot(MemorySaver(), [make_tool()], preamble)

    assert not any(isinstance(m, ModelFallbackMiddleware) for m in create.call_args.kwargs["middleware"])
