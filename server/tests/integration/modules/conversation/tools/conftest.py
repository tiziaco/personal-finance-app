"""The analytics seeds, reused, and a harness running a chat tool the way `create_agent` does: through a ToolNode."""

import uuid
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from app.agents.chatbot.context import TurnContext
from app.modules.conversation.schemas import ToolDisplay
from app.modules.conversation.tools import chat_tools
from tests.integration.modules.analytics.conftest import add, other_user  # noqa: F401


def _compile():
    """A one-node graph over the chat tools; the node injects `runtime` from the call's `context=`.

    Errors propagate (`handle_tool_errors=False`): the tool-events middleware owns turning them into messages.
    """
    graph = StateGraph(MessagesState, context_schema=TurnContext)
    graph.add_node("tools", ToolNode(chat_tools(), handle_tool_errors=False))
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    return graph.compile()


GRAPH = _compile()


@dataclass
class Outcome:
    """What a tool call returned: the model's `content` and the UI's `display`, read back from the artifact."""

    content: str
    artifact: Any

    @property
    def display(self) -> ToolDisplay:
        return ToolDisplay.model_validate(self.artifact)


async def run(name: str, ctx: TurnContext, **args) -> Outcome:
    call = {"name": name, "args": args, "id": str(uuid.uuid4()), "type": "tool_call"}
    state = await GRAPH.ainvoke({"messages": [AIMessage(content="", tool_calls=[call])]}, context=ctx)
    message = state["messages"][-1]
    assert isinstance(message, ToolMessage)
    return Outcome(content=message.content, artifact=message.artifact)
