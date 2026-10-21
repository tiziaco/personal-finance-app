"""Folds the earlier turns into a running summary kept in state; the transcript is never rewritten.

The history endpoint reads the checkpoint, so every message stays in `messages`.
Only the two keys `summary` and `summary_through` are written; the
request-shaping middleware then sends the summary in place of the turns up to
the cutoff. The summariser reads the same stubbed, reasoning-free turns the chat
model is sent, so a figure from a tool result cannot reach the summary.
"""

from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langgraph.config import get_config
from langgraph.runtime import Runtime

from app.agents.chatbot.context import TurnContext
from app.agents.chatbot.middleware.request_shaping import count_tokens, shape_turn, split_turns, turns_after
from app.agents.chatbot.prompts import load_summary_prompt
from app.agents.chatbot.state import ChatState
from app.agents.core import drop_unanswered_tool_calls
from app.core.config import settings
from app.core.logging import logger
from app.integrations.llm import chat_model, with_fallbacks


def render_for_summary(turns: list[list[BaseMessage]]) -> str:
    """Shaped turns as one line per message: `User: …`, `Assistant: …`, `Tool result: <stub>`.

    An assistant message with no text (only tool calls) adds no line.
    """
    lines: list[str] = []
    for turn in turns:
        for message in turn:
            if isinstance(message, HumanMessage):
                lines.append(f"User: {message.text}")
            elif isinstance(message, AIMessage):
                if message.text.strip():
                    lines.append(f"Assistant: {message.text}")
            elif isinstance(message, ToolMessage):
                lines.append(f"Tool result: {message.text}")
    return "\n".join(lines)


class SummaryMiddleware(AgentMiddleware[ChatState, TurnContext]):
    """Before each model call, fold the pending earlier turns into `summary` once they pass the budget.

    Pending turns are the earlier ones after `summary_through`; the current turn
    is never counted or summarised. All pending turns are folded at once, whole,
    so the summary is always current. A failed call is logged and returns
    nothing: the request-shaping middleware then drops the oldest turns to fit.
    `model` defaults to the fallback-wrapped summary model, built on first use.
    """

    state_schema = ChatState

    def __init__(self, *, model: Runnable | None = None) -> None:
        super().__init__()
        self._model = model

    def _summary_model(self) -> Runnable:
        if self._model is None:
            self._model = with_fallbacks(chat_model(settings.llm.CHAT_SUMMARY_MODEL))
        return self._model

    async def abefore_model(self, state: ChatState, runtime: Runtime[TurnContext]) -> dict[str, Any] | None:
        """Return the new `summary` and `summary_through`, or `None` when nothing needs folding."""
        earlier, _ = split_turns(drop_unanswered_tool_calls(state["messages"]))
        pending = [shape_turn(t) for t in turns_after(earlier, state.get("summary_through"))]
        if not pending or sum(count_tokens(t) for t in pending) <= settings.llm.CHAT_HISTORY_MAX_TOKENS:
            return None

        try:
            response = await self._summary_model().ainvoke(
                [
                    SystemMessage(load_summary_prompt()),
                    HumanMessage(
                        f"Summary so far:\n{state.get('summary') or '(none)'}\n\n"
                        f"Turns to fold in:\n{render_for_summary(pending)}"
                    ),
                ]
            )
            return {"summary": response.text.strip(), "summary_through": pending[-1][-1].id}
        except Exception as e:
            try:
                thread_id = get_config()["configurable"]["thread_id"]
            except Exception:
                thread_id = None
            logger.exception("chat_summary_failed", thread_id=thread_id, error=str(e))
            return None
