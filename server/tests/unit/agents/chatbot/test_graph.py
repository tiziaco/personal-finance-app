"""Tests for app.agents.chatbot.graph — tool execution, logging and metrics."""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from prometheus_client import REGISTRY
from pydantic import BaseModel

from app.agents.chatbot.events import ToolFinishedEvent, ToolStartedEvent
from app.agents.chatbot.graph import (
    TOOL_ARGS_LOG_LIMIT,
    TOOL_FAILED_MESSAGE,
    TOOL_UNKNOWN_MESSAGE,
    ChatbotAgent,
    _format_tool_args,
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
from app.agents.messages import Message
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
        assert not any(m.get("tool_calls") for m in sent)
        assert [m["content"] for m in sent[1:]] == ["What did I spend on rent", "Never mind, thanks"]


class TestTitleFor:
    """Tests for `title_for` — a conversation's title from its first exchange."""

    CONVERSATION_ID = uuid.uuid4()
    USER_ID = uuid.uuid4()

    async def test_titles_the_first_exchange_on_the_current_model(self, agent):
        agent.get_chat_history = AsyncMock(
            return_value=[Message(role="user", content="Q"), Message(role="assistant", content="A")]
        )
        with patch("app.agents.chatbot.graph.generate_title", new=AsyncMock(return_value="Budget")) as generate:
            assert await agent.title_for(self.CONVERSATION_ID, self.USER_ID) == "Budget"
        generate.assert_awaited_once_with(
            "Q", "A", agent.llm_service.current_model_name(), self.CONVERSATION_ID, self.USER_ID
        )

    async def test_no_reply_yet_is_none_without_a_model_call(self, agent):
        agent.get_chat_history = AsyncMock(return_value=[Message(role="user", content="Q")])
        with patch("app.agents.chatbot.graph.generate_title", new=AsyncMock()) as generate:
            assert await agent.title_for(self.CONVERSATION_ID, self.USER_ID) is None
        generate.assert_not_awaited()

    async def test_a_model_failure_is_none(self, agent):
        agent.get_chat_history = AsyncMock(
            return_value=[Message(role="user", content="Q"), Message(role="assistant", content="A")]
        )
        with patch("app.agents.chatbot.graph.generate_title", new=AsyncMock(side_effect=RuntimeError("down"))):
            assert await agent.title_for(self.CONVERSATION_ID, self.USER_ID) is None
