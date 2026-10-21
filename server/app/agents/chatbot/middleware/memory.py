"""Long-term memory around a turn: fetch what is relevant before it, write the user's message after."""

import asyncio
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage
from langgraph.config import get_config
from langgraph.runtime import Runtime

from app.agents.chatbot.context import TurnContext
from app.agents.chatbot.state import ChatState
from app.agents.core import get_relevant_memory, update_memory

NO_MEMORY = "No relevant memory found."

# Strong references to the backgrounded writes: the loop keeps only weak ones.
_pending: set[asyncio.Task] = set()


def _last_user_text(state: ChatState) -> str:
    for message in reversed(state["messages"]):
        if isinstance(message, HumanMessage):
            return message.text
    return ""


class MemoryMiddleware(AgentMiddleware[ChatState, TurnContext]):
    """Puts the user's relevant memories in state before the turn and stores the user's message after it.

    Memory sees the user's message and nothing the tools or the model said: tool results and
    replies carry figures the user did not state, which go stale and would be read back as facts.
    """

    state_schema = ChatState

    async def abefore_agent(self, state: ChatState, runtime: Runtime[TurnContext]) -> dict[str, Any]:
        """Fetch what the user's memory holds about this message; the fixed text when nothing."""
        memory = await get_relevant_memory(runtime.context.user_id, _last_user_text(state))
        return {"long_term_memory": memory or NO_MEMORY}

    async def aafter_agent(self, state: ChatState, runtime: Runtime[TurnContext]) -> None:
        """Store the turn's user message, backgrounded."""
        # Backgrounded: the write must not delay the response.
        task = asyncio.create_task(
            update_memory(
                runtime.context.user_id,
                [{"role": "user", "content": _last_user_text(state)}],
                get_config().get("metadata", {}),
            )
        )
        _pending.add(task)
        task.add_done_callback(_pending.discard)
