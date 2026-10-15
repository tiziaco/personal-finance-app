"""This file contains the graph utilities for the application."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    ToolMessage,
)
from langchain_core.messages import trim_messages as _trim_messages

from app.agents.messages import Message
from app.core.config import settings
from app.core.logging import logger


def dump_messages(messages: list[Message]) -> list[dict]:
    """Dump the messages to a list of dictionaries."""
    return [message.model_dump() for message in messages]


def process_llm_response(response: BaseMessage) -> BaseMessage:
    """Flatten structured content blocks back to text.

    GPT-5 models return content as a list of blocks rather than a string —
    ``[{'id': ..., 'summary': [], 'type': 'reasoning'}, {'type': 'text',
    'text': 'actual response'}]`` — and only the text blocks are the answer.
    """
    if isinstance(response.content, list):
        text_parts = []
        for block in response.content:
            if isinstance(block, dict):
                if block.get("type") == "text" and "text" in block:
                    text_parts.append(block["text"])
                elif block.get("type") == "reasoning":
                    logger.debug(
                        "reasoning_block_received",
                        reasoning_id=block.get("id"),
                        has_summary=bool(block.get("summary")),
                    )
            elif isinstance(block, str):
                text_parts.append(block)

        response.content = "".join(text_parts)
        logger.debug(
            "processed_structured_content",
            block_count=len(response.content) if isinstance(response.content, list) else 1,
            extracted_length=len(response.content) if isinstance(response.content, str) else 0,
        )

    return response


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


def prepare_messages(messages: list[Message], llm: BaseChatModel, system_prompt: str) -> list[Message]:
    """Trim the history to the token budget and prepend the system prompt."""
    try:
        trimmed_messages = _trim_messages(
            dump_messages(messages),
            strategy="last",
            token_counter=llm,
            max_tokens=settings.llm.MAX_TOKENS,
            start_on="human",
            include_system=False,
            allow_partial=False,
        )
    except ValueError as e:
        # GPT-5 reasoning blocks the token counter cannot measure. Better to
        # send an untrimmed history than to fail the call.
        if "Unrecognized content block type" in str(e):
            logger.warning(
                "token_counting_failed_skipping_trim",
                error=str(e),
                message_count=len(messages),
            )
            trimmed_messages = messages
        else:
            raise

    return [Message(role="system", content=system_prompt)] + trimmed_messages
