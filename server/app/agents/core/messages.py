"""History repair applied before a thread reaches the model."""

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage


def drop_unanswered_tool_calls(messages: list[BaseMessage]) -> list[BaseMessage]:
    """The history without tool calls that never got their result.

    A turn stopped while its tool ran (Stop, or leaving the conversation: the
    stream's cancellation reaches the graph) leaves the model's tool-call
    message in the checkpoint with no ToolMessage after it. Providers reject
    such a history with a 400, on that turn and on every later one. The call
    is dropped, with any result it did get, and the text the model wrote
    beside it is kept.
    """
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    dropped: set[str] = set()
    kept: list[BaseMessage] = []
    for message in messages:
        if isinstance(message, AIMessage) and any(call["id"] not in answered for call in message.tool_calls):
            dropped.update(call["id"] for call in message.tool_calls)
            if message.text:
                kept.append(AIMessage(content=str(message.text), id=message.id))
            continue
        if isinstance(message, ToolMessage) and message.tool_call_id in dropped:
            continue
        kept.append(message)
    return kept
