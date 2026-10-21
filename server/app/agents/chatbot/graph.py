"""The chat agent's graph: `create_agent` with the chat's middleware, compiled once at startup."""

from collections.abc import Awaitable, Callable, Sequence

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelFallbackMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from app.agents.chatbot.context import TurnContext
from app.agents.chatbot.middleware.memory import MemoryMiddleware
from app.agents.chatbot.middleware.model_timing import ModelTimingMiddleware
from app.agents.chatbot.middleware.request_shaping import RequestShapingMiddleware
from app.agents.chatbot.middleware.summary import SummaryMiddleware
from app.agents.chatbot.middleware.tool_events import ToolEventsMiddleware
from app.agents.chatbot.middleware.turn_bound import TurnBoundMiddleware
from app.agents.chatbot.prompts import load_system_prompt
from app.agents.chatbot.state import ChatState
from app.core.config import settings
from app.core.logging import logger
from app.core.metadata import PROJECT_NAME
from app.integrations.llm import chat_model, fallback_models

# Supersteps a turn may run past what its step cap needs; see `turn_recursion_limit`.
RECURSION_LIMIT_MARGIN = 3


def turn_recursion_limit(max_steps: int) -> int:
    """LangGraph's superstep limit for one turn: a backstop just above the step cap.

    A turn of k model calls runs 3k + 1 supersteps: the memory middleware's
    before_agent node, then for each call the summary middleware's before_model
    node and the model node, a tools superstep between calls, and the after_agent
    node. A turn the cap ends makes `max_steps` calls, so it completes under a
    limit of `3 * max_steps + 1`. The limit follows the setting so that the cap,
    which ends the turn with an answer, is always met first; LangGraph's own
    default (10007 in 1.x) is no backstop at all. A middleware that adds a node
    hook (before_agent, before_model, after_model, after_agent) changes the count:
    revisit this when one does.
    """
    return 3 * max_steps + RECURSION_LIMIT_MARGIN


def build_chatbot(
    checkpointer: BaseCheckpointSaver | None,
    tools: Sequence[BaseTool],
    preamble: Callable[[TurnContext], Awaitable[str]],
    *,
    model: BaseChatModel | None = None,
) -> CompiledStateGraph:
    """Compile the chat agent: the model, the tools and the middleware, over `ChatState` and `TurnContext`.

    The middleware run in list order, the first outermost: the turn bound wraps the
    request shaping, which wraps the timing, which wraps the fallback across models.
    The fallback is `ModelFallbackMiddleware`, which moves to the next model on any
    exception, unlike `with_fallbacks` (an `OpenAIError` only). `model` is the test
    seam; a given model gets no fallbacks. The tool node keeps its default error
    handling, which re-raises a tool's exception to the tool-events middleware.
    """
    if not tools:
        raise ValueError("the chatbot needs at least one tool")

    fallbacks: list[BaseChatModel] = []
    if model is None:
        tuning = {
            "max_tokens": settings.llm.CHAT_REPLY_MAX_TOKENS,
            "reasoning_effort": settings.llm.CHAT_REASONING_EFFORT,
        }
        model = chat_model(**tuning)
        fallbacks = fallback_models(**tuning)

    middleware: list[AgentMiddleware] = [
        MemoryMiddleware(),
        SummaryMiddleware(),
        TurnBoundMiddleware(),
        RequestShapingMiddleware(preamble),
        ModelTimingMiddleware(),
        *([ModelFallbackMiddleware(*fallbacks)] if fallbacks else []),
        ToolEventsMiddleware(),
    ]

    try:
        graph = create_agent(
            model,
            list(tools),
            system_prompt=load_system_prompt(),
            middleware=middleware,
            state_schema=ChatState,
            context_schema=TurnContext,
            checkpointer=checkpointer,
            name=f"{PROJECT_NAME} Agent ({settings.ENVIRONMENT.value})",
        )
    except Exception as e:
        logger.exception("graph_creation_failed", error=str(e), environment=settings.ENVIRONMENT.value)
        raise

    logger.info(
        "graph_created",
        graph_name=f"{PROJECT_NAME} Agent",
        environment=settings.ENVIRONMENT.value,
        has_checkpointer=checkpointer is not None,
    )
    return graph
