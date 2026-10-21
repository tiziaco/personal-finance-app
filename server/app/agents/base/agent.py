"""Base agent class for all LangGraph agents."""

import asyncio
import uuid
from abc import (
    ABC,
    abstractmethod,
)
from typing import (
    AsyncGenerator,
    Iterator,
    Optional,
)

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot
from mem0 import AsyncMemory
from pydantic import ValidationError

from app.agents.chatbot.events import (
    DoneEvent,
    ReasoningEvent,
    StreamEvent,
    TextEvent,
    ToolFinishedEvent,
    ToolStartedEvent,
)
from app.agents.chatbot.toolkit import ToolDisplay, TurnContext
from app.agents.core import (
    create_graph_config,
    get_relevant_memory,
    update_memory,
)
from app.agents.graph import dump_messages
from app.agents.messages import (
    Activity,
    ActivityPart,
    ChatMessage,
    Message,
    ReasoningPart,
    ToolPart,
)
from app.core.logging import logger


def _user_turn(messages: list[Message]) -> list[dict]:
    """What long-term memory sees of a turn: the user's message, nothing the tools or the model said.

    Tool results and replies carry figures the user did not state; stored as memories they go
    stale and would be read back as facts.
    """
    return [{"role": "user", "content": messages[-1].content}]


# Between two of a turn's assistant messages, in the stream and in the history alike;
# and between two parts of one message's reasoning summary.
_TURN_MESSAGE_SEPARATOR = "\n\n"

# The graph node whose model calls are the reply. Any other LLM call made inside
# the graph streams too under stream_mode="messages", and is not for the user.
_CHAT_NODE = "chat"


def _content_text(content: str | list) -> str:
    """The text of a message's content: the string itself, or a block list's text blocks."""
    if isinstance(content, str):
        return content
    return "".join(b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text")


def _summary_items(content: str | list) -> Iterator[tuple[tuple, str]]:
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


def _reasoning_text(content: str | list) -> str:
    """A persisted message's reasoning summary, its items joined as the stream separated them."""
    return _TURN_MESSAGE_SEPARATOR.join(text for _, text in _summary_items(content))


class BaseAgent(ABC):
    """Abstract base class for all LangGraph agents.

    Provides response handling, streaming, chat history and memory management;
    subclasses implement create_graph() for their own workflow. The graph is
    compiled once at application startup, and every method here assumes it.
    """

    def __init__(self):
        self._graph: Optional[CompiledStateGraph] = None
        self.memory: Optional[AsyncMemory] = None

    @abstractmethod
    async def create_graph(self, checkpointer: AsyncPostgresSaver) -> CompiledStateGraph:
        """Create and compile this agent's workflow. Called once, at startup."""
        pass

    def is_ready(self) -> bool:
        """Whether the agent's graph has been compiled and is ready for use."""
        return self._graph is not None

    def _turn_config(self, conversation_id: uuid.UUID, turn_context: TurnContext) -> dict:
        """The graph config for one turn: tracing, the thread, and the turn's context for the nodes."""
        config = create_graph_config(conversation_id, turn_context.user_id)
        config["configurable"]["turn_context"] = turn_context
        return config

    async def get_response(
        self,
        messages: list[Message],
        conversation_id: uuid.UUID,
        turn_context: TurnContext,
    ) -> list[ChatMessage]:
        """Get a response from the agent: the conversation's history, ending with the reply."""
        if not self.is_ready():
            raise RuntimeError(
                "Agent graph not initialized. This should not happen if startup completed successfully."
            )

        user_id = turn_context.user_id
        config = self._turn_config(conversation_id, turn_context)

        relevant_memory = (await get_relevant_memory(user_id, messages[-1].content)) or "No relevant memory found."

        try:
            response = await self._graph.ainvoke(
                input={"messages": dump_messages(messages), "long_term_memory": relevant_memory, "turn_steps": 0},
                config=config,
            )
            # Backgrounded: the memory write must not delay the response.
            asyncio.create_task(update_memory(user_id, _user_turn(messages), config["metadata"]))
            return self._process_messages(response["messages"], stopped=response.get("stopped", {}))
        except Exception as e:
            logger.exception("error_getting_response", error=str(e), conversation_id=conversation_id)
            raise

    async def get_stream_response(
        self,
        messages: list[Message],
        conversation_id: uuid.UUID,
        turn_context: TurnContext,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream the turn as typed events (`app.agents.chatbot.events`), ending with `DoneEvent`.

        The chat node's model output becomes `ReasoningEvent`s and `TextEvent`s; the
        tool node's `ToolStartedEvent`s and `ToolFinishedEvent`s arrive on the custom
        stream and pass through as they are. A tool call the node announced nothing
        for (an unknown tool name) produces no event, only its ToolMessage, which is
        never streamed.

        A response the step cap or a repeat drops (it is not persisted) has already
        streamed by the time the node decides: its reasoning is shown, rightly, since
        that thinking happened; its text, if it wrote any beside its tool calls, is
        shown too and is missing when the conversation is reopened. Holding text back
        until each response is complete would delay every answer for that rare case.
        """
        if not self.is_ready():
            raise RuntimeError(
                "Agent graph not initialized. This should not happen if startup completed successfully."
            )

        user_id = turn_context.user_id
        config = self._turn_config(conversation_id, turn_context)

        relevant_memory = (await get_relevant_memory(user_id, messages[-1].content)) or "No relevant memory found."

        try:
            # The message the last text came from. A turn can hold several (text
            # written before a tool call, then the answer); the history joins
            # them with a blank line, and so does the stream.
            last_text_id: Optional[str] = None
            # The summary item the last reasoning came from, until another event
            # interrupts it: a new item in the same run starts a new paragraph.
            last_reasoning_key: Optional[tuple] = None
            async for mode, payload in self._graph.astream(
                {"messages": dump_messages(messages), "long_term_memory": relevant_memory, "turn_steps": 0},
                config=config,
                stream_mode=["messages", "custom"],
            ):
                if mode == "custom":
                    if isinstance(payload, ToolStartedEvent | ToolFinishedEvent):
                        last_reasoning_key = None
                        yield payload
                    continue

                message, metadata = payload
                # Every message a node produces arrives here, tool results included.
                # Only the chat node's model output is the reply.
                if not isinstance(message, AIMessage) or metadata.get("langgraph_node") != _CHAT_NODE:
                    continue

                for item_key, delta in _summary_items(message.content):
                    key = (message.id, *item_key)
                    separator = _TURN_MESSAGE_SEPARATOR if last_reasoning_key not in (None, key) else ""
                    last_reasoning_key = key
                    yield ReasoningEvent(text=separator + delta)

                text = message.text
                if not text:
                    continue
                separator = _TURN_MESSAGE_SEPARATOR if last_text_id not in (None, message.id) else ""
                last_text_id = message.id
                last_reasoning_key = None
                yield TextEvent(text=separator + text)

            state: StateSnapshot = await self._graph.aget_state(config=config)
            values = state.values or {}
            if values.get("messages"):
                asyncio.create_task(update_memory(user_id, _user_turn(messages), config["metadata"]))
            final_id = values["messages"][-1].id if values.get("messages") else None
            yield DoneEvent(stopped=final_id is not None and final_id in values.get("stopped", {}))
        except Exception as stream_error:
            logger.exception("error_in_stream_processing", error=str(stream_error), conversation_id=conversation_id)
            raise stream_error

    async def get_chat_history(self, conversation_id: uuid.UUID) -> list[ChatMessage]:
        """Get the chat history for a given conversation."""
        if not self.is_ready():
            raise RuntimeError(
                "Agent graph not initialized. This should not happen if startup completed successfully."
            )

        state: StateSnapshot = await self._graph.aget_state(
            config={"configurable": {"thread_id": str(conversation_id)}}
        )
        if not state.values:
            return []
        return self._process_messages(state.values["messages"], stopped=state.values.get("stopped", {}))

    def _tool_title(self, name: str) -> Optional[str]:
        """The display title of a call to this tool in a reply's activity, or None to leave it out.

        An agent whose stream announces only some tool calls returns None for the
        rest, so a reopened conversation shows the same rows, with the same titles,
        the stream did.
        """
        return name

    def _process_messages(self, messages: list[BaseMessage], stopped: dict[str, str]) -> list[ChatMessage]:
        """Rebuild the history the client shows: each user message, then the turn's reply.

        A turn's assistant messages (text written before a tool call, then the
        answer) fold into one reply, its text joined as get_stream_response
        streamed it, its reasoning and tool calls in order in `activity`, marked
        `stopped` when its final message is in `stopped`. A turn with no final
        answer, one the user stopped, adds no reply and no activity: the
        checkpoint still holds its tool calls and any results, and showing them
        would leave rows with no answer below them.
        """
        processed: list[ChatMessage] = []
        turn: list[BaseMessage] = []
        for message in messages:
            if isinstance(message, HumanMessage):
                processed.extend(self._reply(turn, stopped))
                turn = []
                if content := _content_text(message.content):
                    processed.append(ChatMessage(role="user", content=content))
            else:
                turn.append(message)
        processed.extend(self._reply(turn, stopped))
        return processed

    def _reply(self, turn: list[BaseMessage], stopped: dict[str, str]) -> list[ChatMessage]:
        """The one reply a turn's messages make, or none if it has no final answer."""
        final = turn[-1] if turn else None
        if not (isinstance(final, AIMessage) and not final.tool_calls and _content_text(final.content)):
            return []

        results = {m.tool_call_id: m for m in turn if isinstance(m, ToolMessage)}
        texts: list[str] = []
        parts: list[ActivityPart] = []
        for message in turn:
            if not isinstance(message, AIMessage):
                continue
            if text := _content_text(message.content):
                texts.append(text)
            if reasoning := _reasoning_text(message.content):
                parts.append(ReasoningPart(text=reasoning))
            for call in message.tool_calls:
                result = results.get(call["id"])
                title = self._tool_title(call["name"])
                if result is not None and title is not None:
                    parts.append(self._tool_part(call, title, result))

        is_stopped = final.id is not None and final.id in stopped
        activity = Activity(parts=parts, stopped=is_stopped) if parts or is_stopped else None
        return [ChatMessage(role="assistant", content=_TURN_MESSAGE_SEPARATOR.join(texts), activity=activity)]

    @staticmethod
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
