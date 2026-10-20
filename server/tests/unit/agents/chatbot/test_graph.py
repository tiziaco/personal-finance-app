"""Tests for app.agents.chatbot.graph — tool execution, logging and metrics."""

import asyncio
import datetime as dt
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from prometheus_client import REGISTRY
from pydantic import BaseModel, ValidationError

from app.agents.chatbot.events import DoneEvent, TextEvent, ToolFinishedEvent, ToolStartedEvent
from app.agents.chatbot.graph import (
    STOPPED_FALLBACK_TEXT,
    TOOL_ARGS_LOG_LIMIT,
    TOOL_FAILED_MESSAGE,
    TOOL_UNKNOWN_MESSAGE,
    ChatbotAgent,
    _format_tool_args,
    repeated_call,
)
from app.agents.chatbot.state import GraphState
from app.agents.chatbot.toolkit import (
    AgentTool,
    SummaryItem,
    ToolArgumentError,
    ToolDisplay,
    Toolkit,
    ToolOutcome,
    TurnContext,
)
from app.agents.graph import drop_unanswered_tool_calls
from app.agents.messages import Activity, ChatMessage, Message, ToolPart
from app.core.config import LLMSettings, settings
from app.integrations.llm.service import LLMRegistry

pytestmark = pytest.mark.unit


class IntArgs(BaseModel):
    n: int


def _display(title: str = "Test") -> ToolDisplay:
    return ToolDisplay(title=title, period=None, summary=[SummaryItem(kind="count", value=1)], table=None)


def make_tool(name: str, run, *, args_schema: type[BaseModel] = IntArgs) -> AgentTool:
    return AgentTool(name=name, title=f"{name} title", description="d", args_schema=args_schema, run=run)


async def _ok(args: IntArgs, ctx: TurnContext) -> ToolOutcome:
    return ToolOutcome(content=f"n is {args.n}", display=_display())


def _agent_with(*tools: AgentTool) -> ChatbotAgent:
    return ChatbotAgent(Toolkit(tools=list(tools), preamble=Toolkit.empty().preamble))


CTX = TurnContext(user_id=uuid.uuid4(), session_factory=MagicMock())
THREAD_ID = uuid.uuid4()


def _tool_calls(tool_name: str, outcome: str = "error") -> int:
    """The count for a tool's outcome, or 0 before it has ever been seen.

    Read as a delta around the call under test: `app/core/metrics.py` registers
    on the default registry at import, so counters accumulate across every test
    in the process and an absolute assertion would depend on test order.
    """
    value = REGISTRY.get_sample_value("tool_calls_total", {"tool": tool_name, "outcome": outcome})
    return int(value or 0)


@pytest.fixture
def agent() -> ChatbotAgent:
    """A real ChatbotAgent with no tools.

    Constructible without a credential: `bind_tools` records the tools and
    leaves the client to be built on first use.
    """
    return ChatbotAgent(Toolkit.empty())


class TestInvokeTool:
    """Tests for `_invoke_tool` — the unit that owns one tool call."""

    async def test_success_carries_the_display_as_artifact(self):
        agent = _agent_with(make_tool("t", _ok))

        message = await agent._invoke_tool({"name": "t", "args": {"n": 3}, "id": "c1"}, CTX)

        assert message.content == "n is 3"
        assert message.status == "success"
        assert message.tool_call_id == "c1"
        assert message.artifact == _display().model_dump()

    async def test_invalid_arguments_return_the_validation_message(self):
        agent = _agent_with(make_tool("t", _ok))
        before = _tool_calls("t", "invalid_args")

        message = await agent._invoke_tool({"name": "t", "args": {"n": "x"}, "id": "c1"}, CTX)

        assert message.status == "error"
        assert message.content.startswith("Invalid arguments: n:")
        assert message.content != TOOL_FAILED_MESSAGE
        assert _tool_calls("t", "invalid_args") == before + 1

    async def test_tool_argument_error_text_reaches_the_model(self):
        async def run(args, ctx):
            raise ToolArgumentError("no data before 2025-03-01")

        message = await _agent_with(make_tool("t", run))._invoke_tool({"name": "t", "args": {"n": 1}, "id": "c1"}, CTX)

        assert message.content == "no data before 2025-03-01"
        assert message.status == "error"

    async def test_crash_still_returns_the_fixed_message(self):
        async def run(args, ctx):
            raise RuntimeError("db down")

        agent = _agent_with(make_tool("crashy", run))
        before = _tool_calls("crashy")

        message = await agent._invoke_tool({"name": "crashy", "args": {"n": 1}, "id": "c2"}, CTX)

        assert message.status == "error"
        assert message.content == TOOL_FAILED_MESSAGE
        assert "db down" not in message.content
        assert _tool_calls("crashy") == before + 1

    async def test_a_call_without_a_turn_context_is_a_crash_not_an_exception(self):
        agent = _agent_with(make_tool("t", _ok))

        message = await agent._invoke_tool({"name": "t", "args": {"n": 1}, "id": "c1"}, None)

        assert message.status == "error"
        assert message.content == TOOL_FAILED_MESSAGE

    async def test_unknown_tool_does_not_raise(self, agent):
        """A name the model invented used to raise KeyError out of the graph."""
        message = await agent._invoke_tool({"name": "no_such_tool", "args": {}, "id": "call_3"}, CTX)

        assert message.status == "error"
        assert message.content == TOOL_UNKNOWN_MESSAGE
        assert REGISTRY.get_sample_value("tool_calls_total", {"tool": "no_such_tool", "outcome": "unknown_tool"})


class TestToolCallNode:
    """Tests for `_tool_call` — all calls of a message, concurrently, with stream events."""

    @staticmethod
    def _state(*names: str) -> GraphState:
        calls = [{"name": n, "args": {"n": i}, "id": f"c{i}"} for i, n in enumerate(names)]
        return GraphState(messages=[AIMessage(content="", tool_calls=calls)])

    @staticmethod
    def _config() -> dict:
        return {"configurable": {"thread_id": "t1", "turn_context": CTX}}

    async def test_tool_calls_run_concurrently_and_one_crash_does_not_sink_the_other(self):
        started = {"a": asyncio.Event(), "b": asyncio.Event()}

        async def waits(name: str, args, ctx):
            started[name].set()
            # Completes only if the other call has started too: sequential execution would hang.
            await asyncio.wait_for(asyncio.gather(*(e.wait() for e in started.values())), timeout=2)
            return await _ok(args, ctx)

        async def crashes(args, ctx):
            await asyncio.wait_for(started["a"].wait(), timeout=2)
            raise RuntimeError("boom")

        agent = _agent_with(
            make_tool("a", lambda args, ctx: waits("a", args, ctx)),
            make_tool("b", lambda args, ctx: waits("b", args, ctx)),
            make_tool("c", crashes),
        )

        with patch("app.agents.chatbot.graph.get_stream_writer", return_value=MagicMock()):
            command = await agent._tool_call(self._state("a", "b", "c"), self._config())

        messages = command.update["messages"]
        assert [m.tool_call_id for m in messages] == ["c0", "c1", "c2"]
        assert [m.status for m in messages] == ["success", "success", "error"]
        assert messages[2].content == TOOL_FAILED_MESSAGE
        assert command.goto == "chat"

    async def test_tool_node_emits_started_and_finished_events(self):
        async def crashes(args, ctx):
            raise RuntimeError("boom")

        agent = _agent_with(make_tool("good", _ok), make_tool("bad", crashes))
        writer = MagicMock()

        with patch("app.agents.chatbot.graph.get_stream_writer", return_value=writer):
            await agent._tool_call(self._state("good", "bad"), self._config())

        events = [c.args[0] for c in writer.call_args_list]
        assert ToolStartedEvent(id="c0", name="good", title="good title") in events
        assert ToolFinishedEvent(id="c0", ok=True, display=_display()) in events
        assert ToolStartedEvent(id="c1", name="bad", title="bad title") in events
        assert ToolFinishedEvent(id="c1", ok=False, display=None) in events
        assert events.index(ToolStartedEvent(id="c0", name="good", title="good title")) < events.index(
            ToolFinishedEvent(id="c0", ok=True, display=_display())
        )


class TestToolBinding:
    def test_no_web_search_tool_is_bound(self):
        assert "duckduckgo" not in str(ChatbotAgent(Toolkit.empty()).llm_service._tools)

    def test_toolkit_tools_are_bound_as_schemas(self):
        schemas = ChatbotAgent(
            Toolkit(tools=[make_tool("t", _ok)], preamble=Toolkit.empty().preamble)
        ).llm_service._tools

        assert [s["function"]["name"] for s in schemas] == ["t"]
        assert schemas[0]["function"]["parameters"]["properties"]["n"]["type"] == "integer"


class TestFormatToolArgs:
    """Tests for the log rendering of tool arguments."""

    def test_short_args_are_rendered_whole(self):
        assert _format_tool_args({"query": "example query"}) == '{"query": "example query"}'

    def test_long_args_are_truncated(self):
        rendered = _format_tool_args({"query": "x" * 500})

        assert len(rendered) == TOOL_ARGS_LOG_LIMIT + 3
        assert rendered.endswith("...")


class TestChat:
    """Tests for `_chat` — what the chat node sends to the model."""

    @pytest.mark.asyncio
    async def test_chat_does_not_send_a_tool_call_left_without_a_result(self, agent):
        """Stop during a tool call, then send again: the next call must not 400.

        The chat node's AIMessage is checkpointed before the tool node runs; a
        cancelled tool node leaves it there with no ToolMessage, and the next
        turn appends a HumanMessage after it.
        """
        agent.llm_service = MagicMock()
        agent.llm_service.get_llm.return_value = LLMRegistry.get(LLMRegistry.get_all_names()[0])
        agent.llm_service.current_model_name.return_value = LLMRegistry.get_all_names()[0]
        agent.llm_service.call = AsyncMock(return_value=AIMessage(content="Sure."))
        state = GraphState(
            messages=[
                HumanMessage(content="What did I spend on rent"),
                AIMessage(content="", tool_calls=[{"name": "some_tool", "args": {"query": "rent"}, "id": "call_1"}]),
                HumanMessage(content="Never mind, thanks"),
            ]
        )

        await agent._chat(state, {"configurable": {"thread_id": "t1"}})

        sent = agent.llm_service.call.call_args.args[0]
        assert not any(getattr(m, "tool_calls", None) for m in sent)
        # [static prompt, history..., turn context, current turn]
        assert [m.content for m in sent[1:-2]] == ["What did I spend on rent"]
        assert sent[-1].content == "Never mind, thanks"

    @pytest.mark.asyncio
    async def test_chat_puts_date_and_memory_in_a_message_after_the_history_without_a_turn_context(self, agent):
        """No turn context yet (nothing sets it before the route does): no preamble, no error."""
        agent.llm_service = MagicMock()
        agent.llm_service.get_llm.return_value = LLMRegistry.get(LLMRegistry.get_all_names()[0])
        agent.llm_service.current_model_name.return_value = LLMRegistry.get_all_names()[0]
        agent.llm_service.call = AsyncMock(return_value=AIMessage(content="Sure."))
        state = GraphState(messages=[HumanMessage(content="hi")], long_term_memory="Saving for a flat")

        await agent._chat(state, {"configurable": {"thread_id": "t1"}})

        sent = agent.llm_service.call.call_args.args[0]
        assert "Saving for a flat" not in sent[0].content and "{" not in sent[0].content
        assert str(dt.date.today()) in sent[1].content and "Saving for a flat" in sent[1].content
        assert sent[2].content == "hi"


def _call(name: str, n: int, call_id: str) -> dict:
    return {"name": name, "args": {"n": n}, "id": call_id}


class TestRepeatedCall:
    def test_the_same_name_and_args_since_the_last_human_message_repeats(self):
        messages = [
            HumanMessage(content="q"),
            AIMessage(content="", tool_calls=[_call("t", 1, "a")]),
            ToolMessage(content="r", tool_call_id="a"),
            AIMessage(content="", tool_calls=[_call("t", 1, "b")]),
        ]
        assert repeated_call(messages)

    def test_different_args_or_name_is_not_a_repeat(self):
        messages = [
            HumanMessage(content="q"),
            AIMessage(content="", tool_calls=[_call("t", 1, "a")]),
            ToolMessage(content="r", tool_call_id="a"),
            AIMessage(content="", tool_calls=[_call("t", 2, "b"), _call("u", 1, "c")]),
        ]
        assert not repeated_call(messages)

    def test_a_call_from_an_earlier_turn_does_not_count(self):
        messages = [
            HumanMessage(content="q"),
            AIMessage(content="", tool_calls=[_call("t", 1, "a")]),
            ToolMessage(content="r", tool_call_id="a"),
            AIMessage(content="done"),
            HumanMessage(content="again"),
            AIMessage(content="", tool_calls=[_call("t", 1, "b")]),
        ]
        assert not repeated_call(messages)


class TestTurnLimits:
    """The loop end to end on a MemorySaver: step cap, repeat detection, wrap-up."""

    @staticmethod
    async def _run(
        agent: ChatbotAgent, llm_responses, text: str = "q", thread: str = "t1", recursion_limit=None, **extra
    ):
        """Run one turn on the agent's graph; `llm_responses(with_tools, n)` makes each model reply."""
        name = LLMRegistry.get_all_names()[0]
        agent.llm_service = MagicMock()
        agent.llm_service.get_llm.return_value = LLMRegistry.get(name)
        agent.llm_service.current_model_name.return_value = name
        calls: list[bool] = []

        async def call(messages, *args, with_tools=True, **kwargs):
            calls.append(with_tools)
            return llm_responses(with_tools, len(calls))

        agent.llm_service.call = AsyncMock(side_effect=call)
        graph = agent._graph or await agent.create_graph(MemorySaver())
        config = {"configurable": {"thread_id": thread, "turn_context": CTX}}
        if recursion_limit is not None:
            config["recursion_limit"] = recursion_limit
        state = await graph.ainvoke(
            {"messages": [HumanMessage(content=text)], "turn_steps": 0, **extra}, config=config
        )
        return state, calls, config

    @staticmethod
    def _counting_agent() -> tuple[ChatbotAgent, list[int]]:
        ran: list[int] = []

        async def run(args: IntArgs, ctx: TurnContext) -> ToolOutcome:
            ran.append(args.n)
            return await _ok(args, ctx)

        return _agent_with(make_tool("t", run)), ran

    async def test_step_cap_ends_the_turn_with_a_wrap_up_answer_marked_stopped(self, monkeypatch):
        monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 2)
        agent, ran = self._counting_agent()

        def respond(with_tools, n):
            if not with_tools:
                return AIMessage(content="Partial answer.")
            return AIMessage(content="", tool_calls=[_call("t", n, f"c{n}")])

        state, calls, _ = await self._run(agent, respond)

        last = state["messages"][-1]
        assert last.text == "Partial answer." and not last.tool_calls
        assert state["stopped"] == {last.id: "step_limit"}
        assert calls == [True, True, False]
        assert ran == [1]

    async def test_a_long_cap_is_what_ends_the_turn_not_langgraphs_recursion_limit(self, monkeypatch):
        # 20 steps take 39 supersteps, past a fixed limit of 25: the turn's limit must follow the cap.
        monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 20)
        agent, ran = self._counting_agent()
        with patch("app.agents.shared.observability.langfuse.CallbackHandler"):
            limit = agent._turn_config(THREAD_ID, CTX)["recursion_limit"]

        def respond(with_tools, n):
            if not with_tools:
                return AIMessage(content="Partial answer.")
            return AIMessage(content="", tool_calls=[_call("t", n, f"c{n}")])

        state, _, _ = await self._run(agent, respond, recursion_limit=limit)

        assert state["stopped"] == {state["messages"][-1].id: "step_limit"}
        assert len(ran) == 19
        # A backstop, not a bound the cap could never reach: it sits just above the turn's supersteps.
        assert 2 * 20 <= limit < 2 * 20 + 10

    def test_the_step_cap_setting_is_at_least_one(self):
        with pytest.raises(ValidationError):
            LLMSettings(CHAT_MAX_STEPS=0)

    async def test_repeated_identical_call_stops_the_loop(self):
        agent, ran = self._counting_agent()

        def respond(with_tools, n):
            if not with_tools:
                return AIMessage(content="Partial answer.")
            return AIMessage(content="", tool_calls=[_call("t", 7, f"c{n}")])

        state, calls, _ = await self._run(agent, respond)

        last = state["messages"][-1]
        assert state["stopped"] == {last.id: "repeated_call"}
        assert ran == [7]
        assert calls == [True, True, False]

    async def test_a_failing_wrap_up_falls_back_to_the_fixed_text(self, monkeypatch):
        monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 1)
        agent, _ = self._counting_agent()

        def respond(with_tools, n):
            if not with_tools:
                raise RuntimeError("model down")
            return AIMessage(content="", tool_calls=[_call("t", n, f"c{n}")])

        state, _, _ = await self._run(agent, respond)

        last = state["messages"][-1]
        assert last.content == STOPPED_FALLBACK_TEXT
        assert state["stopped"] == {last.id: "step_limit"}

    async def test_turn_steps_reset_on_each_turn(self, monkeypatch):
        monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 2)
        agent, _ = self._counting_agent()

        def respond(with_tools, n):
            # Each turn: one tool step, then an answer.
            return AIMessage(content="", tool_calls=[_call("t", n, f"c{n}")]) if n % 2 else AIMessage(content="ok")

        await self._run(agent, respond)
        state, _, _ = await self._run(agent, lambda w, n: respond(w, n), text="again")

        assert not state.get("stopped")
        assert state["messages"][-1].text == "ok"

    async def test_the_next_turn_works_after_a_stopped_one(self, monkeypatch):
        monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 1)
        agent, _ = self._counting_agent()

        def stops(with_tools, n):
            return (
                AIMessage(content="Partial.")
                if not with_tools
                else AIMessage(content="", tool_calls=[_call("t", n, f"c{n}")])
            )

        await self._run(agent, stops)
        state, _, _ = await self._run(agent, lambda w, n: AIMessage(content="Fine."), text="next")

        sent = drop_unanswered_tool_calls(state["messages"])
        assert not any(isinstance(m, AIMessage) and m.tool_calls for m in sent)
        assert state["messages"][-1].text == "Fine."

    async def test_the_answering_model_labels_the_metric(self):
        agent, _ = self._counting_agent()
        before = REGISTRY.get_sample_value("llm_inference_duration_seconds_count", {"model": "answering-model"}) or 0

        await self._run(
            agent,
            lambda w, n: AIMessage(content="hi", response_metadata={"model_name": "answering-model"}),
        )

        after = REGISTRY.get_sample_value("llm_inference_duration_seconds_count", {"model": "answering-model"})
        assert after == before + 1


class TestEmptyReply:
    """A reply with no text and no tool calls is a failed model call, not an answer."""

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
    async def test_the_turn_fails_and_nothing_empty_is_checkpointed(self, reply):
        agent = _agent_with(make_tool("t", _ok))

        with pytest.raises(Exception, match="empty"):
            await TestStreamAndHistory._stream(agent, lambda w, n: reply)

        history = await agent.get_chat_history(THREAD_ID)
        assert [m.role for m in history] == ["user"]

    async def test_it_is_logged_with_the_model_and_the_incomplete_reason(self):
        agent = _agent_with(make_tool("t", _ok))
        reply = AIMessage(
            content="",
            response_metadata={"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}},
        )

        with patch("app.agents.chatbot.graph.logger") as log, pytest.raises(Exception, match="empty"):
            await TestStreamAndHistory._stream(agent, lambda w, n: reply)

        [call] = [c for c in log.warning.call_args_list if c.args[0] == "llm_empty_response"]
        assert call.kwargs["model"] == LLMRegistry.get_all_names()[0]
        assert call.kwargs["status"] == "incomplete"
        assert call.kwargs["incomplete_details"] == {"reason": "max_output_tokens"}

    async def test_an_empty_wrap_up_falls_back_to_the_fixed_text(self, monkeypatch):
        monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 1)
        agent = _agent_with(make_tool("t", _ok))

        def respond(with_tools, n):
            return AIMessage(content="") if not with_tools else AIMessage(content="", tool_calls=[_call("t", n, "c")])

        events = await TestStreamAndHistory._stream(agent, respond)

        assert events == [TextEvent(text=STOPPED_FALLBACK_TEXT), DoneEvent(stopped=True)]


class TestStreamAndHistory:
    """The typed stream and the history on the real graph: what reaches the client."""

    @staticmethod
    async def _stream(agent: ChatbotAgent, llm_responses, text: str = "q") -> list:
        name = LLMRegistry.get_all_names()[0]
        agent.llm_service = MagicMock()
        agent.llm_service.get_llm.return_value = LLMRegistry.get(name)
        agent.llm_service.current_model_name.return_value = name
        calls: list[bool] = []

        async def call(messages, *args, with_tools=True, **kwargs):
            calls.append(with_tools)
            return llm_responses(with_tools, len(calls))

        agent.llm_service.call = AsyncMock(side_effect=call)
        if agent._graph is None:
            await agent.create_graph(MemorySaver())
        with (
            patch("app.agents.base.agent.get_relevant_memory", new=AsyncMock(return_value="")),
            patch("app.agents.base.agent.update_memory", new=AsyncMock()),
        ):
            return [
                event
                async for event in agent.get_stream_response([Message(role="user", content=text)], THREAD_ID, CTX)
            ]

    async def test_a_tool_turn_streams_tool_events_then_the_answer(self):
        agent = _agent_with(make_tool("t", _ok))

        def respond(with_tools, n):
            return AIMessage(content="", tool_calls=[_call("t", 1, "c1")]) if n == 1 else AIMessage(content="Done.")

        events = await self._stream(agent, respond)

        assert events == [
            ToolStartedEvent(id="c1", name="t", title="t title"),
            ToolFinishedEvent(id="c1", ok=True, display=_display()),
            TextEvent(text="Done."),
            DoneEvent(stopped=False),
        ]
        [_, reply] = await agent.get_chat_history(THREAD_ID)
        assert reply.activity.parts == [ToolPart(id="c1", name="t", title="t title", ok=True, display=_display())]

    async def test_a_turn_the_server_stopped_is_done_stopped_and_reopens_stopped(self, monkeypatch):
        monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 1)
        agent = _agent_with(make_tool("t", _ok))

        def respond(with_tools, n):
            if not with_tools:
                return AIMessage(content="Partial.")
            return AIMessage(content="", tool_calls=[_call("t", n, f"c{n}")])

        events = await self._stream(agent, respond)

        assert events == [TextEvent(text="Partial."), DoneEvent(stopped=True)]
        [_, reply] = await agent.get_chat_history(THREAD_ID)
        assert reply.content == "Partial."
        assert reply.activity == Activity(parts=[], stopped=True)

    async def test_an_unknown_tool_is_in_neither_the_stream_nor_the_history(self):
        agent = _agent_with(make_tool("t", _ok))

        def respond(with_tools, n):
            return (
                AIMessage(content="", tool_calls=[_call("invented", 1, "c1")]) if n == 1 else AIMessage(content="OK.")
            )

        events = await self._stream(agent, respond)

        assert events == [TextEvent(text="OK."), DoneEvent(stopped=False)]
        [_, reply] = await agent.get_chat_history(THREAD_ID)
        assert reply.activity is None


class TestTitleFor:
    """Tests for `title_for` — a conversation's title from its first exchange."""

    CONVERSATION_ID = uuid.uuid4()
    USER_ID = uuid.uuid4()

    async def test_titles_the_first_exchange_on_the_current_model(self, agent):
        agent.get_chat_history = AsyncMock(
            return_value=[ChatMessage(role="user", content="Q"), ChatMessage(role="assistant", content="A")]
        )
        with patch("app.agents.chatbot.graph.generate_title", new=AsyncMock(return_value="Budget")) as generate:
            assert await agent.title_for(self.CONVERSATION_ID, self.USER_ID) == "Budget"
        generate.assert_awaited_once_with(
            "Q", "A", agent.llm_service.current_model_name(), self.CONVERSATION_ID, self.USER_ID
        )

    async def test_no_reply_yet_is_none_without_a_model_call(self, agent):
        agent.get_chat_history = AsyncMock(return_value=[ChatMessage(role="user", content="Q")])
        with patch("app.agents.chatbot.graph.generate_title", new=AsyncMock()) as generate:
            assert await agent.title_for(self.CONVERSATION_ID, self.USER_ID) is None
        generate.assert_not_awaited()

    async def test_a_model_failure_is_none(self, agent):
        agent.get_chat_history = AsyncMock(
            return_value=[ChatMessage(role="user", content="Q"), ChatMessage(role="assistant", content="A")]
        )
        with patch("app.agents.chatbot.graph.generate_title", new=AsyncMock(side_effect=RuntimeError("down"))):
            assert await agent.title_for(self.CONVERSATION_ID, self.USER_ID) is None
