"""Tests for app.agents.chatbot.graph — tool execution, logging and metrics."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from prometheus_client import REGISTRY

from app.agents.chatbot.graph import (
    TOOL_ARGS_LOG_LIMIT,
    TOOL_FAILED_MESSAGE,
    TOOL_UNKNOWN_MESSAGE,
    ChatbotAgent,
    _format_tool_args,
)
from app.agents.chatbot.state import GraphState
from app.agents.chatbot.tools import tools
from app.integrations.llm.service import LLMRegistry

pytestmark = pytest.mark.unit


@tool
def ok_tool(text: str) -> str:
    """Return the input unchanged."""
    return f"result for {text}"


@tool
def exploding_tool(text: str) -> str:
    """Always fail."""
    raise RuntimeError("upstream is down")


def _tool_calls(tool_name: str) -> int:
    """The `error`-outcome count for a tool, or 0 before it has ever been seen.

    Read as a delta around the call under test: `app/core/metrics.py` registers
    on the default registry at import, so counters accumulate across every test
    in the process and an absolute assertion would depend on test order.
    """
    value = REGISTRY.get_sample_value("tool_calls_total", {"tool": tool_name, "outcome": "error"})
    return int(value or 0)


@pytest.fixture
def agent() -> ChatbotAgent:
    """A real ChatbotAgent.

    Constructible without a credential: `bind_tools` records the tools and
    leaves the client to be built on first use.
    """
    return ChatbotAgent()


class TestInvokeTool:
    """Tests for `_invoke_tool` — the unit that owns one tool call."""

    @pytest.mark.asyncio
    async def test_tool_result_is_returned_to_the_model(self, agent):
        agent.tools_by_name["ok_tool"] = ok_tool

        message = await agent._invoke_tool({"name": "ok_tool", "args": {"text": "hi"}, "id": "call_1"})

        assert message.content == "result for hi"
        assert message.status == "success"
        assert message.tool_call_id == "call_1"

    @pytest.mark.asyncio
    async def test_tool_failure_returns_an_error_message(self, agent):
        """A raising tool must not escape the node, and must be visibly an error.

        With `handle_tool_error=True` on the tool a failure came back as an
        ordinary success-status message carrying the exception text, so a search
        failing every time was indistinguishable from one working.
        """
        agent.tools_by_name["exploding_tool"] = exploding_tool
        before = _tool_calls("exploding_tool")

        message = await agent._invoke_tool({"name": "exploding_tool", "args": {"text": "hi"}, "id": "call_2"})

        assert message.status == "error"
        assert message.content == TOOL_FAILED_MESSAGE
        assert "upstream is down" not in message.content
        assert _tool_calls("exploding_tool") == before + 1

    @pytest.mark.asyncio
    async def test_unknown_tool_does_not_raise(self, agent):
        """A name the model invented used to raise KeyError out of the graph."""
        message = await agent._invoke_tool({"name": "no_such_tool", "args": {}, "id": "call_3"})

        assert message.status == "error"
        assert message.content == TOOL_UNKNOWN_MESSAGE
        assert REGISTRY.get_sample_value("tool_calls_total", {"tool": "no_such_tool", "outcome": "unknown_tool"})


class TestToolConfiguration:
    """Tests for the tools themselves, not the node."""

    @pytest.mark.parametrize("configured_tool", tools, ids=lambda t: t.name)
    def test_tools_do_not_swallow_their_own_errors(self, configured_tool):
        """No tool may set `handle_tool_error`.

        It makes LangChain catch the exception and return it as a plain string
        result, so `_invoke_tool`'s except branch never runs: the call is counted
        a success and the raw upstream error is handed to the model and persisted
        into the checkpoint. Every assertion about failure handling in this file
        is void for a tool that sets it, and nothing else would tell you.
        """
        assert not configured_tool.handle_tool_error


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
        """Stop during a web search, then send again: the next call must not 400.

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
                HumanMessage(content="Search rent prices"),
                AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "rent"}, "id": "call_1"}]),
                HumanMessage(content="Never mind, thanks"),
            ]
        )

        await agent._chat(state, {"configurable": {"thread_id": "t1"}})

        sent = agent.llm_service.call.call_args.args[0]
        assert not any(m.get("tool_calls") for m in sent)
        assert [m["content"] for m in sent[1:]] == ["Search rent prices", "Never mind, thanks"]
