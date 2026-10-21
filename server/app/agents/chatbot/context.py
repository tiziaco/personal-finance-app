"""What the chat model is sent: the static prompt, the history, a per-turn context, the current turn.

The current turn (the last human message and everything after it) always goes
whole: trimming inside it could drop the very question being answered. Earlier
turns are what the budget is spent on: their tool results become one-line stubs
(the figures must come from a tool call made this turn, and the checkpoint
keeps the full result for the UI) and, if the history is still over budget,
the oldest turns are dropped whole.
"""

import datetime as dt
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agents.core import drop_unanswered_tool_calls
from app.core.logging import logger


@dataclass
class TurnContext:
    """What a tool may use during one chat turn; built once per turn by the route.

    The user is never a tool argument: tools read `user_id` from here, so no
    wording of a question can reach another user's data.
    """

    user_id: uuid.UUID
    session_factory: async_sessionmaker
    # The per-turn load of the user's analytics history: a `Future` the chat's tools
    # set and share. `Any` because `agents` does not know the type.
    history: Any = None


STUB_TEMPLATE = "{title}{period}: result omitted from an earlier turn; call the tool again for figures."

# Characters per token for the estimate: coarse, but it only has to keep the
# history bounded when the model's own counter cannot measure it.
CHARS_PER_TOKEN = 4

TokenCounter = Callable[[list[BaseMessage]], int]


def _reasoning_text(block: dict) -> str:
    return "".join(part.get("text", "") for part in block.get("summary") or [] if isinstance(part, dict))


def _message_text(message: BaseMessage) -> str:
    """The message's text plus its reasoning summaries, for the estimate."""
    content = message.content
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            if block.get("type") == "reasoning":
                parts.append(_reasoning_text(block))
            else:
                parts.append(str(block.get("text", "")))
    return "".join(parts)


def estimate_tokens(messages: list[BaseMessage]) -> int:
    """Roughly how many tokens the messages take: characters over four, tool calls included."""
    chars = 0
    for message in messages:
        chars += len(_message_text(message))
        if isinstance(message, AIMessage):
            chars += sum(len(str(call["name"])) + len(str(call["args"])) for call in message.tool_calls)
    return chars // CHARS_PER_TOKEN + 1


def with_estimate_fallback(count_tokens: TokenCounter) -> TokenCounter:
    """A counter that falls back to `estimate_tokens` when the model's own cannot measure the messages.

    The fallback is the normal path, not a fault: the model's counter cannot measure
    reasoning blocks, which every model step of a reasoning turn carries. So DEBUG.
    """

    def count(messages: list[BaseMessage]) -> int:
        try:
            return count_tokens(messages)
        except Exception as e:
            logger.debug("token_counting_failed_estimating", error=str(e), message_count=len(messages))
            return estimate_tokens(messages)

    return count


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


def _split_turns(messages: list[BaseMessage]) -> tuple[list[list[BaseMessage]], list[BaseMessage]]:
    """Earlier turns (each starting at a human message) and the current turn (from the last one)."""
    last_human = max((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=None)
    if last_human is None:
        return [], messages
    earlier: list[list[BaseMessage]] = []
    for message in messages[:last_human]:
        if isinstance(message, HumanMessage) or not earlier:
            earlier.append([])
        earlier[-1].append(message)
    return earlier, messages[last_human:]


def build_model_context(
    messages: list[BaseMessage],
    *,
    system_prompt: str,
    turn_context_text: str,
    budget_tokens: int,
    count_tokens: TokenCounter,
) -> list[BaseMessage]:
    """The messages for one model call: `[system, *earlier turns, turn context, *current turn]`.

    The system prompt is first and static so the provider can cache it; the
    per-turn text follows the history. Earlier turns lose their reasoning blocks
    and their tool results (stubbed), then are dropped oldest first until the
    whole fits `budget_tokens`. The current turn is never changed or trimmed.
    """
    earlier, current = _split_turns(drop_unanswered_tool_calls(messages))

    prepared: list[list[BaseMessage]] = []
    for turn in earlier:
        tool_names = {call["id"]: call["name"] for m in turn if isinstance(m, AIMessage) for call in m.tool_calls}
        prepared.append(
            [
                _stub(m, tool_names)
                if isinstance(m, ToolMessage)
                else _without_reasoning(m)
                if isinstance(m, AIMessage)
                else m
                for m in turn
            ]
        )

    head = SystemMessage(content=system_prompt)
    turn_context = SystemMessage(content=turn_context_text)

    # Each part counted once, then turns dropped by subtraction rather than by
    # re-counting the whole. A sum of counts runs slightly over the whole's (each
    # count adds the reply's priming tokens), which errs towards trimming.
    total = count_tokens([head, turn_context, *current])
    sizes = [count_tokens(turn) for turn in prepared]
    total += sum(sizes)
    while prepared and total > budget_tokens:
        total -= sizes.pop(0)
        prepared.pop(0)
    return [head, *(m for turn in prepared for m in turn), turn_context, *current]


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
