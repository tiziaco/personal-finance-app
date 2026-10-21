"""The chat as the client sees it, built from the agent's own types: the history and the stream events.

Pure: checkpoint messages and the graph's stream items in, the wire models of
`conversation.schemas` out. The agent knows nothing of the wire; the tool titles
come in as a map (`ChatbotAgent.tool_titles`), so this never imports the tools (R10).
This is the one place that reads reasoning: the provider's raw `content` blocks,
`{"type": "reasoning", "index", "summary": [{"index", "text"}]}`, since the
standard `content_blocks` lose the boundaries between summary items.
"""

from collections.abc import AsyncIterator, Iterator, Mapping
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from pydantic import ValidationError

from app.agents.chatbot.middleware.tool_events import ToolCallFinished, ToolCallStarted
from app.core.logging import logger
from app.modules.conversation.schemas import (
    Activity,
    ActivityPart,
    ChatMessage,
    DoneEvent,
    ReasoningEvent,
    ReasoningPart,
    StreamEvent,
    TextEvent,
    ToolDisplay,
    ToolFinishedEvent,
    ToolPart,
    ToolStartedEvent,
)

# Between two of a turn's assistant messages, in the stream and in the history alike;
# and between two parts of one message's reasoning summary.
TURN_MESSAGE_SEPARATOR = "\n\n"

# The graph node whose model calls are the reply. Any other LLM call made inside
# the graph streams too under stream_mode="messages", and is not for the user.
MODEL_NODE = "model"

# What the last reasoning key becomes after a text event: text ends a reasoning
# paragraph, so the next reasoning delta, whatever its key, starts a new one.
_AFTER_TEXT = "text"


def content_text(content: str | list) -> str:
    """The text of a message's content: the string itself, or a block list's text blocks."""
    if isinstance(content, str):
        return content
    return "".join(b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text")


def summary_items(content: str | list) -> Iterator[tuple[tuple, str]]:
    """Each reasoning summary item's (block index, item index) key and text, in order.

    Streamed, an item's text is a delta and the key says which item it extends;
    persisted, the provider has merged them into one block holding every item whole.
    """
    if isinstance(content, str):
        return
    for block in content:
        if not (isinstance(block, dict) and block.get("type") == "reasoning"):
            continue
        for position, item in enumerate(block.get("summary") or []):
            if isinstance(item, dict) and item.get("text"):
                yield (block.get("index"), item.get("index", position)), item["text"]


def reasoning_text(content: str | list) -> str:
    """A persisted message's reasoning summary, its items joined as the stream separated them."""
    return TURN_MESSAGE_SEPARATOR.join(text for _, text in summary_items(content))


# ── The history ───────────────────────────────────────────────────────────────


def history(messages: list[BaseMessage], stopped: dict[str, str], titles: Mapping[str, str]) -> list[ChatMessage]:
    """Rebuild the history the client shows: each user message, then the turn's reply.

    A turn's assistant messages (text written before a tool call, then the
    answer) fold into one reply, its text joined as `events` streamed it, its
    reasoning and tool calls in order in `activity`, marked `stopped` when its
    final message is in `stopped`. A turn with no final answer, one the user
    stopped, adds no reply and no activity: the checkpoint still holds its tool
    calls and any results, and showing them would leave rows with no answer
    below them. A tool call whose name has no entry in `titles` (one the model
    invented) adds no part, as the stream announced nothing for it.
    """
    processed: list[ChatMessage] = []
    turn: list[BaseMessage] = []
    for message in messages:
        if isinstance(message, HumanMessage):
            processed.extend(_reply(turn, stopped, titles))
            turn = []
            if content := content_text(message.content):
                processed.append(ChatMessage(role="user", content=content))
        else:
            turn.append(message)
    processed.extend(_reply(turn, stopped, titles))
    return processed


def _reply(turn: list[BaseMessage], stopped: dict[str, str], titles: Mapping[str, str]) -> list[ChatMessage]:
    """The one reply a turn's messages make, or none if it has no final answer."""
    final = turn[-1] if turn else None
    if not (isinstance(final, AIMessage) and not final.tool_calls and content_text(final.content)):
        return []

    results = {m.tool_call_id: m for m in turn if isinstance(m, ToolMessage)}
    texts: list[str] = []
    parts: list[ActivityPart] = []
    for message in turn:
        if not isinstance(message, AIMessage):
            continue
        if text := content_text(message.content):
            texts.append(text)
        if reasoning := reasoning_text(message.content):
            parts.append(ReasoningPart(text=reasoning))
        for call in message.tool_calls:
            result = results.get(call["id"])
            title = titles.get(call["name"])
            if result is not None and title is not None:
                parts.append(_tool_part(call, title, result))

    is_stopped = final.id is not None and final.id in stopped
    activity = Activity(parts=parts, stopped=is_stopped) if parts or is_stopped else None
    return [ChatMessage(role="assistant", content=TURN_MESSAGE_SEPARATOR.join(texts), activity=activity)]


def _tool_part(call: dict, title: str, result: ToolMessage) -> ToolPart:
    """A tool call's part; its display is the result's artifact, if that still validates."""
    ok = result.status != "error"
    display = None
    if ok and result.artifact is not None:
        try:
            display = ToolDisplay.model_validate(result.artifact)
        except ValidationError:
            # An older checkpoint's display shape: the row stays, without its figures.
            logger.warning("chat_history_tool_display_invalid", tool_name=call["name"], tool_call_id=call["id"])
    return ToolPart(id=call["id"], name=call["name"], title=title, ok=ok, display=display)


def first_exchange(history: list[ChatMessage]) -> tuple[str, str] | None:
    """The first reply and the user message it answered, or None before any reply.

    Paired, not taken separately: a first turn stopped before its reply leaves
    a question with no answer, and the title must not mix two turns.
    """
    for index, message in enumerate(history):
        if message.role == "assistant":
            question = next((m.content for m in reversed(history[:index]) if m.role == "user"), None)
            return (question, message.content) if question else None
    return None


# ── The stream ────────────────────────────────────────────────────────────────


def _stream_display(event: ToolCallFinished) -> ToolDisplay | None:
    """A finished call's display, or None when it failed or its artifact does not validate (logged)."""
    if not event.ok or event.artifact is None:
        return None
    try:
        return ToolDisplay.model_validate(event.artifact)
    except ValidationError:
        logger.warning("chat_stream_tool_display_invalid", tool_call_id=event.id)
        return None


async def events(stream: AsyncIterator[tuple[str, Any]], titles: Mapping[str, str]) -> AsyncIterator[StreamEvent]:
    """The turn's wire events from the graph's `("messages", …)` and `("custom", …)` stream items.

    The model node's output becomes `ReasoningEvent`s and `TextEvent`s; the
    tool-events middleware's `ToolCallStarted`/`ToolCallFinished` become
    `tool_started` (with the tool's title) and `tool_finished` (with the artifact
    as a `ToolDisplay`). A call the middleware announced nothing for (an unknown
    tool name) produces no event, only its ToolMessage, which is never streamed.
    No `done`: the route reads the saved state for it once the stream ends.

    A response the step cap or a repeat drops (it is not persisted) has already
    streamed by the time the middleware decides: its reasoning is shown, rightly,
    since that thinking happened; its text, if it wrote any beside its tool calls,
    is shown too and is missing when the conversation is reopened. Holding text
    back until each response is complete would delay every answer for that rare case.
    """
    # The message the last text came from. A turn can hold several (text written
    # before a tool call, then the answer); the history joins them with a blank
    # line, and so does the stream.
    last_text_id: str | None = None
    # The summary item the last reasoning came from, until another event interrupts
    # it: a tool event resets it (reasoning either side of a tool row is two parts),
    # a text event ends the paragraph, and a new item starts a new paragraph.
    last_reasoning_key: tuple | str | None = None
    async for mode, payload in stream:
        if mode == "custom":
            if isinstance(payload, ToolCallStarted):
                title = titles.get(payload.name)
                if title is not None:
                    last_reasoning_key = None
                    yield ToolStartedEvent(id=payload.id, name=payload.name, title=title)
            elif isinstance(payload, ToolCallFinished):
                last_reasoning_key = None
                yield ToolFinishedEvent(id=payload.id, ok=payload.ok, display=_stream_display(payload))
            continue

        message, metadata = payload
        # Every message a node produces arrives here, tool results included.
        # Only the model node's output is the reply.
        if not isinstance(message, AIMessage) or metadata.get("langgraph_node") != MODEL_NODE:
            continue

        for item_key, delta in summary_items(message.content):
            key = (message.id, *item_key)
            separator = TURN_MESSAGE_SEPARATOR if last_reasoning_key not in (None, key) else ""
            last_reasoning_key = key
            yield ReasoningEvent(text=separator + delta)

        text = message.text
        if not text:
            continue
        separator = TURN_MESSAGE_SEPARATOR if last_text_id not in (None, message.id) else ""
        last_text_id = message.id
        last_reasoning_key = _AFTER_TEXT
        yield TextEvent(text=separator + text)


def done(messages: list[BaseMessage], stopped: dict[str, str]) -> DoneEvent:
    """The stream's last event: `stopped` when the server ended the turn whose answer is last in the thread."""
    return DoneEvent(stopped=bool(messages) and messages[-1].id in stopped)
