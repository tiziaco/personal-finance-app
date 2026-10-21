"""Tests for app.agents.chatbot.middleware.memory — long-term memory around a turn."""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from app.agents.chatbot.context import TurnContext
from app.agents.chatbot.middleware import memory as memory_module
from app.agents.chatbot.middleware.memory import NO_MEMORY, MemoryMiddleware
from app.agents.chatbot.state import ChatState

pytestmark = pytest.mark.unit

USER_ID = uuid.uuid4()
MODULE = "app.agents.chatbot.middleware.memory"


def _runtime():
    return SimpleNamespace(context=TurnContext(user_id=USER_ID, session_factory=MagicMock()))


def _state():
    return {
        "messages": [
            HumanMessage("earlier question"),
            AIMessage("earlier answer"),
            HumanMessage("how much did I spend?"),
            AIMessage("", tool_calls=[{"name": "t", "args": {}, "id": "c1"}]),
            ToolMessage("EUR 412.50", tool_call_id="c1"),
            AIMessage("You spent EUR 412.50."),
        ]
    }


async def test_before_agent_puts_the_relevant_memory_in_state():
    fetch = AsyncMock(return_value="* saving for a flat")
    with patch(f"{MODULE}.get_relevant_memory", fetch):
        update = await MemoryMiddleware().abefore_agent(_state(), _runtime())

    assert update == {"long_term_memory": "* saving for a flat"}
    fetch.assert_awaited_once_with(USER_ID, "how much did I spend?")


async def test_before_agent_uses_the_fixed_text_when_memory_is_empty():
    with patch(f"{MODULE}.get_relevant_memory", AsyncMock(return_value="")):
        update = await MemoryMiddleware().abefore_agent(_state(), _runtime())

    assert update == {"long_term_memory": NO_MEMORY}


async def test_after_agent_sends_memory_only_this_turns_user_message():
    write = AsyncMock()
    metadata = {"user_id": "u", "conversation_id": "c"}
    with (
        patch(f"{MODULE}.update_memory", write),
        patch(f"{MODULE}.get_config", return_value={"metadata": {**metadata, "langgraph_step": 3}}),
    ):
        assert await MemoryMiddleware().aafter_agent(_state(), _runtime()) is None
        await asyncio.gather(*memory_module._pending)

    write.assert_awaited_once_with(USER_ID, [{"role": "user", "content": "how much did I spend?"}], metadata)
    assert not memory_module._pending


async def test_the_write_inside_a_graph_run_carries_the_routes_metadata_only():
    """Inside a node LangGraph adds its own keys to the config's metadata; none may reach mem0."""
    write = AsyncMock()
    middleware = MemoryMiddleware()
    runtime = _runtime()

    async def node(state):
        await middleware.aafter_agent(state, runtime)
        return {}

    graph = StateGraph(ChatState)
    graph.add_node("node", node)
    graph.add_edge(START, "node")
    graph.add_edge("node", END)
    route_metadata = {"user_id": str(USER_ID), "conversation_id": "c1", "langfuse_tags": ["test"]}

    with patch(f"{MODULE}.update_memory", write):
        await graph.compile().ainvoke(
            {"messages": [HumanMessage("hello")]},
            config={"metadata": route_metadata, "configurable": {"thread_id": "c1"}},
        )
        await asyncio.gather(*memory_module._pending)

    write.assert_awaited_once_with(USER_ID, [{"role": "user", "content": "hello"}], route_metadata)


async def test_a_turn_without_a_user_message_neither_fetches_nor_writes():
    fetch, write = AsyncMock(), AsyncMock()
    state = {"messages": [AIMessage("hi")]}
    with patch(f"{MODULE}.get_relevant_memory", fetch), patch(f"{MODULE}.update_memory", write):
        update = await MemoryMiddleware().abefore_agent(state, _runtime())
        await MemoryMiddleware().aafter_agent(state, _runtime())

    assert update == {"long_term_memory": NO_MEMORY}
    fetch.assert_not_called()
    write.assert_not_called()
    assert not memory_module._pending


async def test_a_memory_failure_is_logged_and_the_turn_proceeds():
    # The real get_relevant_memory, with the store failing: it logs and returns "".
    with (
        patch("app.agents.core.memory.create_memory", AsyncMock(side_effect=RuntimeError("store down"))),
        patch("app.agents.core.memory.logger") as log,
    ):
        update = await MemoryMiddleware().abefore_agent(_state(), _runtime())

    assert update == {"long_term_memory": NO_MEMORY}
    assert log.exception.call_args.args == ("failed_to_get_relevant_memory",)
