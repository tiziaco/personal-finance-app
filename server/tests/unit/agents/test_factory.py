"""Tests for app.agents.factory — the agents built at startup, with the toolkits injected into them."""

import pytest
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

from app.agents.chatbot.toolkit import AgentTool, Toolkit
from app.agents.factory import initialize_agents

pytestmark = pytest.mark.unit


class _Args(BaseModel):
    n: int


async def _run(args, ctx):
    raise AssertionError("not called")


def _toolkit(*names: str) -> Toolkit:
    tools = [AgentTool(name=n, title=n, description="d", args_schema=_Args, run=_run) for n in names]
    return Toolkit(tools=tools, preamble=Toolkit.empty().preamble)


async def test_the_chatbot_runs_with_the_toolkit_it_is_given():
    toolkit = _toolkit("lookup", "search")

    agents = await initialize_agents(MemorySaver(), {"chatbot": toolkit})

    chatbot = agents["chatbot"]
    assert chatbot.is_ready()
    assert chatbot.toolkit is toolkit
    assert [schema["function"]["name"] for schema in chatbot.llm_service._tools] == ["lookup", "search"]


async def test_an_agent_without_a_toolkit_fails_at_startup():
    """A lost entry in main's agent_toolkits must not start an agent that answers from nothing."""
    with pytest.raises(KeyError, match="chatbot"):
        await initialize_agents(MemorySaver(), {})
