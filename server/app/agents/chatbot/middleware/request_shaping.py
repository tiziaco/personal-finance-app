"""What the chat model is sent each call: summary, earlier turns (shaped), turn context, the current turn.

The request is shaped from `request.messages`, never from state, so a wrap-up
instruction a surrounding hook appended survives at the end. The current turn
(the last human message and everything after it) always goes whole: trimming
inside it could drop the very question being answered. Earlier turns are what
the budget is spent on: their tool results become one-line stubs (the figures
must come from a tool call made this turn, and the checkpoint keeps the full
result for the UI), their reasoning blocks go, and if they are still over
budget the oldest are dropped whole. The system prompt stays on
`request.system_message`.
"""

import datetime as dt
from collections.abc import Awaitable, Callable
from itertools import chain

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages.utils import count_tokens_approximately
from langgraph.config import get_config

from app.agents.chatbot.context import TurnContext
from app.agents.chatbot.state import ChatState
from app.agents.core import drop_unanswered_tool_calls
from app.core.config import settings
from app.core.logging import logger

STUB_TEMPLATE = "{title}{period}: result omitted from an earlier turn; call the tool again for figures."
SUMMARY_PREFIX = "Earlier in this conversation: "

count_tokens = count_tokens_approximately


def _without_reasoning(message: AIMessage) -> AIMessage:
    """The AI message without its reasoning blocks; tool calls stay so their results still pair."""
    if not isinstance(message.content, list) or not any(
        isinstance(b, dict) and b.get("type") == "reasoning" for b in message.content
    ):
        return message
    text = "".join(
        b if isinstance(b, str) else str(b.get("text", ""))
        for b in message.content
        if isinstance(b, str) or (isinstance(b, dict) and b.get("type") == "text")
    )
    return message.model_copy(update={"content": text})


def _stub(message: ToolMessage, tool_names: dict[str, str]) -> ToolMessage:
    """One line for an earlier turn's tool result, named from its display or, for an error, its tool."""
    artifact = message.artifact if isinstance(message.artifact, dict) else {}
    title = artifact.get("title") or tool_names.get(message.tool_call_id) or message.name or "Tool"
    period = f" · {artifact['period']}" if artifact.get("period") else ""
    return ToolMessage(
        content=STUB_TEMPLATE.format(title=title, period=period),
        tool_call_id=message.tool_call_id,
        name=message.name,
        id=message.id,
    )


def split_turns(messages: list[BaseMessage]) -> tuple[list[list[BaseMessage]], list[BaseMessage]]:
    """Earlier turns (each starting at a human message) and the current turn (from the last one).

    Without any human message everything is the current turn.
    """
    last_human = max((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=None)
    if last_human is None:
        return [], messages
    earlier: list[list[BaseMessage]] = []
    for message in messages[:last_human]:
        if isinstance(message, HumanMessage) or not earlier:
            earlier.append([])
        earlier[-1].append(message)
    return earlier, messages[last_human:]


def shape_turn(turn: list[BaseMessage]) -> list[BaseMessage]:
    """An earlier turn as the model sees it: tool results stubbed, reasoning blocks gone, tool calls kept.

    A stub is named from the result's display artifact (title and period), else
    the call's tool name, else the message's name, else `"Tool"`.
    """
    tool_names = {call["id"]: call["name"] for m in turn if isinstance(m, AIMessage) for call in m.tool_calls}
    return [
        _stub(m, tool_names)
        if isinstance(m, ToolMessage)
        else _without_reasoning(m)
        if isinstance(m, AIMessage)
        else m
        for m in turn
    ]


def turns_after(turns: list[list[BaseMessage]], summary_through: str | None) -> list[list[BaseMessage]]:
    """The turns that follow the message whose id is `summary_through`.

    All of them when it is `None` or names no message in `turns` (a cutoff that
    no longer matches the history means no cutoff).
    """
    if summary_through is None:
        return turns
    for i, turn in enumerate(turns):
        if any(m.id == summary_through for m in turn):
            return turns[i + 1 :]
    return turns


def render_turn_context(*, today: dt.date, memory: str, preamble: str) -> str:
    """The per-turn message: today's date, the toolkit's preamble (finished month, data span) and memory."""
    sections = [f"Today's date: {today.isoformat()}."]
    if preamble.strip():
        sections.append(preamble.strip())
    sections.append(
        "What you know about the user (goals and circumstances; never a source of figures):\n"
        + (memory.strip() or "Nothing yet.")
    )
    return "\n\n".join(sections)


class RequestShapingMiddleware(AgentMiddleware[ChatState, TurnContext]):
    """Rewrites each model request: `[summary?, *earlier turns shaped, turn context, *current turn]`.

    Only the request changes; no state is written. `preamble` is the toolkit's
    per-turn text (finished month, data span); one that fails is left out, so
    the turn is still answered with today's date and the user's memory, and a
    tool that needs the same data fails on its own and the model is told so.
    """

    state_schema = ChatState

    def __init__(self, preamble: Callable[[TurnContext], Awaitable[str]]) -> None:
        super().__init__()
        self._preamble = preamble

    async def awrap_model_call(
        self,
        request: ModelRequest[TurnContext],
        handler: Callable[[ModelRequest[TurnContext]], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Send the shaped messages on to the model."""
        earlier, current = split_turns(drop_unanswered_tool_calls(request.messages))
        shaped = [shape_turn(t) for t in turns_after(earlier, request.state.get("summary_through"))]
        # The budget is spent on the shaped earlier turns alone: the rest is never trimmable.
        while shaped and sum(count_tokens(t) for t in shaped) > settings.llm.CHAT_HISTORY_MAX_TOKENS:
            shaped.pop(0)

        try:
            preamble = await self._preamble(request.runtime.context)
        except Exception as e:
            preamble = ""
            logger.exception("chat_preamble_failed", thread_id=get_config()["configurable"]["thread_id"], error=str(e))

        turn_context = SystemMessage(
            render_turn_context(
                today=dt.date.today(), memory=request.state.get("long_term_memory", ""), preamble=preamble
            )
        )
        summary = [SystemMessage(SUMMARY_PREFIX + s)] if (s := request.state.get("summary")) else []
        return await handler(
            request.override(messages=[*summary, *chain.from_iterable(shaped), turn_context, *current])
        )
