"""Tests for app.agents.chatbot.agent — what `ChatbotAgent` hands the graph and returns from it."""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver

from app.agents.chatbot import ChatbotAgent, TurnContext, build_chatbot
from app.agents.chatbot.graph import turn_recursion_limit
from app.core.config import settings
from tests.fakes.chat_model import ScriptedChatModel

pytestmark = pytest.mark.unit

CONVERSATION_ID = uuid.uuid4()
CTX = TurnContext(user_id=uuid.uuid4(), session_factory=MagicMock())


def _tool(name: str, title: str) -> StructuredTool:
    async def run() -> str:
        return ""

    return StructuredTool.from_function(coroutine=run, name=name, description="d", metadata={"title": title})


class _Graph:
    """Records what the agent passes; answers with fixed values."""

    def __init__(self, values=None):
        self.values = values or {}
        self.calls: list[tuple[str, tuple, dict]] = []

    async def astream(self, *args, **kwargs):
        self.calls.append(("astream", args, kwargs))
        yield "messages", (AIMessage("hi"), {"langgraph_node": "model"})

    async def ainvoke(self, *args, **kwargs):
        self.calls.append(("ainvoke", args, kwargs))
        return self.values

    async def aget_state(self, *args, **kwargs):
        self.calls.append(("aget_state", args, kwargs))
        return SimpleNamespace(values=self.values)


@pytest.fixture(autouse=True)
def no_langfuse_client():
    with patch("app.agents.core.observability.CallbackHandler"):
        yield


def test_tool_titles_map_each_name_to_its_metadata_title():
    agent = ChatbotAgent(_Graph(), [_tool("a", "A title"), _tool("b", "B title")])

    assert agent.tool_titles == {"a": "A title", "b": "B title"}


async def test_stream_passes_the_context_the_thread_and_the_recursion_limit():
    graph = _Graph()
    agent = ChatbotAgent(graph, [])

    items = [item async for item in agent.stream("hello", CONVERSATION_ID, CTX)]

    assert items == [("messages", (AIMessage("hi"), {"langgraph_node": "model"}))]
    [(_, args, kwargs)] = graph.calls
    assert args == ({"messages": [HumanMessage("hello")]},)
    assert kwargs["context"] is CTX
    assert kwargs["stream_mode"] == ["messages", "custom"]
    assert kwargs["config"]["configurable"]["thread_id"] == str(CONVERSATION_ID)
    assert kwargs["config"]["recursion_limit"] == turn_recursion_limit(settings.llm.CHAT_MAX_STEPS)
    assert kwargs["config"]["metadata"]["user_id"] == str(CTX.user_id)


async def test_run_returns_the_messages_and_stopped():
    final = AIMessage("Partial.", id="f")
    graph = _Graph({"messages": [HumanMessage("q"), final], "stopped": {"f": "step_limit"}})

    messages, stopped = await ChatbotAgent(graph, []).run("q", CONVERSATION_ID, CTX)

    assert messages == [HumanMessage("q"), final]
    assert stopped == {"f": "step_limit"}
    [(_, _, kwargs)] = graph.calls
    assert kwargs["context"] is CTX
    assert kwargs["config"]["recursion_limit"] == turn_recursion_limit(settings.llm.CHAT_MAX_STEPS)


async def test_run_without_a_stopped_key_is_not_stopped():
    graph = _Graph({"messages": [HumanMessage("q"), AIMessage("a")]})

    _, stopped = await ChatbotAgent(graph, []).run("q", CONVERSATION_ID, CTX)

    assert stopped == {}


async def test_state_reads_the_thread():
    graph = _Graph({"messages": [HumanMessage("q")], "stopped": {"x": "repeated_call"}})

    assert await ChatbotAgent(graph, []).state(CONVERSATION_ID) == ([HumanMessage("q")], {"x": "repeated_call"})
    [(_, _, kwargs)] = graph.calls
    assert kwargs["config"] == {"configurable": {"thread_id": str(CONVERSATION_ID)}}


async def test_state_of_an_unknown_thread_is_empty():
    assert await ChatbotAgent(_Graph({}), []).state(CONVERSATION_ID) == ([], {})


async def test_a_failing_graph_raises_from_the_stream():
    class _Failing(_Graph):
        async def astream(self, *args, **kwargs):
            yield "messages", (AIMessage("partial"), {"langgraph_node": "model"})
            raise RuntimeError("model down")

    agent = ChatbotAgent(_Failing(), [])
    received = []

    with pytest.raises(RuntimeError, match="model down"):
        async for item in agent.stream("q", CONVERSATION_ID, CTX):
            received.append(item)

    assert received == [("messages", (AIMessage("partial"), {"langgraph_node": "model"}))]


async def test_a_stream_cancelled_by_an_anyio_cancel_scope_cancels_the_model_call():
    """sse-starlette cancels a disconnected client's stream through an anyio cancel scope.

    The scope cancels again at every await inside it, which on a bare `graph.astream` cuts
    LangGraph's own cleanup short and leaves the model call running for nobody.
    """
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def slow_model() -> AIMessage:
        started.set()
        try:
            await asyncio.sleep(30)  # a model still generating
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return AIMessage("never")

    async def preamble(ctx: TurnContext) -> str:
        return ""

    tools = [_tool("t", "T")]
    graph = build_chatbot(MemorySaver(), tools, preamble, model=ScriptedChatModel(responses=[slow_model]))
    agent = ChatbotAgent(graph, tools)

    async def consume() -> None:
        async for _ in agent.stream("q", CONVERSATION_ID, CTX):
            pass

    with (
        patch("app.agents.chatbot.middleware.memory.get_relevant_memory", AsyncMock(return_value="")),
        patch("app.agents.chatbot.middleware.memory.update_memory", AsyncMock()),
    ):
        async with anyio.create_task_group() as group:
            group.start_soon(consume)
            await asyncio.wait_for(started.wait(), timeout=2)
            group.cancel_scope.cancel()

        await asyncio.wait_for(cancelled.wait(), timeout=2)


async def test_a_producer_killed_by_a_non_exception_releases_the_consumer():
    """A cancellation of the producer task from outside is not an `Exception`; the consumer must still end."""

    class _Killed(_Graph):
        async def astream(self, *args, **kwargs):
            yield "messages", (AIMessage("partial"), {"langgraph_node": "model"})
            raise asyncio.CancelledError

    agent = ChatbotAgent(_Killed(), [])
    received = []

    async def consume() -> None:
        async for item in agent.stream("q", CONVERSATION_ID, CTX):
            received.append(item)

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(consume(), timeout=2)

    assert received == [("messages", (AIMessage("partial"), {"langgraph_node": "model"}))]
