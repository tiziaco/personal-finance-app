"""`ChatbotAgent`: the compiled chat graph and the three ways a route uses it."""

import asyncio
import uuid
from collections.abc import AsyncIterator, Sequence
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from app.agents.chatbot.context import TurnContext
from app.agents.chatbot.graph import turn_recursion_limit
from app.agents.core import create_graph_config
from app.core.config import settings
from app.core.logging import logger


class ChatbotAgent:
    """Holds the graph compiled at startup; runs a turn, streams one, and reads a thread's state.

    It returns the graph's own types (messages, `stopped`, stream tuples): what the
    client sees is built from them by `conversation`. `tool_titles` maps each tool's
    name to its display title, from the tools the graph was compiled with.
    """

    def __init__(self, graph: CompiledStateGraph, tools: Sequence[BaseTool]):
        self.graph = graph
        self.tool_titles: dict[str, str] = {tool.name: tool.metadata["title"] for tool in tools}
        logger.info(
            "chatbot_agent_initialized",
            model=settings.llm.DEFAULT_LLM_MODEL,
            environment=settings.ENVIRONMENT.value,
        )

    def _turn_config(self, conversation_id: uuid.UUID, context: TurnContext) -> dict:
        """The turn's config: the thread, tracing and metadata, bounded by the limit that follows `CHAT_MAX_STEPS`."""
        config = create_graph_config(conversation_id, context.user_id)
        config["recursion_limit"] = turn_recursion_limit(settings.llm.CHAT_MAX_STEPS)
        return config

    async def stream(
        self, message: str, conversation_id: uuid.UUID, context: TurnContext
    ) -> AsyncIterator[tuple[str, Any]]:
        """The turn as the graph streams it: `("messages", (message, metadata))` and `("custom", event)` pairs.

        The graph runs in a task of its own and its items reach the caller through a
        queue. A caller that stops listening (sse-starlette, on a client disconnect,
        cancels through an anyio cancel scope) cancels that task once. Iterated
        directly, the graph's stream would take the scope's cancellation at every
        await of LangGraph's own cleanup, which then never cancels the model call in
        flight; a single cancellation of the task lets the cleanup run, and the call stops.

        The producer runs ahead of the consumer by design: the queue is unbounded, and
        what it holds is bounded by one turn's output.
        """
        items: asyncio.Queue[tuple[bool, Any]] = asyncio.Queue()

        async def run_graph() -> None:
            try:
                async for item in self.graph.astream(
                    {"messages": [HumanMessage(message)]},
                    config=self._turn_config(conversation_id, context),
                    context=context,
                    stream_mode=["messages", "custom"],
                ):
                    items.put_nowait((True, item))
            except Exception as e:
                items.put_nowait((False, e))
            except BaseException as e:
                # A cancellation from outside or an exception group: release the consumer, then let it unwind.
                items.put_nowait((False, e))
                raise
            else:
                items.put_nowait((False, None))

        task = asyncio.create_task(run_graph())
        try:
            while True:
                more, item = await items.get()
                if not more:
                    if item is not None:
                        raise item
                    return
                yield item
        finally:
            task.cancel()

    async def run(
        self, message: str, conversation_id: uuid.UUID, context: TurnContext
    ) -> tuple[list[BaseMessage], dict[str, str]]:
        """Run the turn to its end; the thread's messages and `stopped` after it."""
        values = await self.graph.ainvoke(
            {"messages": [HumanMessage(message)]},
            config=self._turn_config(conversation_id, context),
            context=context,
        )
        return values["messages"], values.get("stopped", {})

    async def state(self, conversation_id: uuid.UUID) -> tuple[list[BaseMessage], dict[str, str]]:
        """The thread's messages and `stopped` from its checkpoint; empty for a thread with none."""
        snapshot = await self.graph.aget_state(config={"configurable": {"thread_id": str(conversation_id)}})
        if not snapshot.values:
            return [], {}
        return snapshot.values.get("messages", []), snapshot.values.get("stopped", {})
