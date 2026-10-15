"""A short title for a conversation, written by the model from its first exchange."""

import re
import uuid

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from app.agents.messages import Message
from app.agents.shared.observability import create_graph_config
from app.integrations.llm import LLMRegistry

# The rename route's limit: a generated title must be one a user could have typed.
TITLE_MAX_LENGTH = 100
# Enough of each message to know the topic; a title needs no more.
TITLE_INPUT_LIMIT = 1000

TITLE_PROMPT = (
    "You name chat conversations. Reply with a title of at most 6 words that says what the "
    "conversation is about. Reply with the title only: no quotes, no trailing punctuation, "
    "no prefix such as 'Title:'."
)

_QUOTES = "\"'“”‘’«»`"


def clean_title(raw: str) -> str:
    """Normalise a model's title: one line, no quotes, prefix or trailing punctuation, capped."""
    title = " ".join(raw.split())
    # Until nothing changes: each rule can expose what another strips, as in
    # '"Budget tips".' (a quote behind a full stop) or '"Title: Rent"'.
    previous = None
    while title != previous:
        previous = title
        title = re.sub(r"^title:\s*", "", title, flags=re.IGNORECASE)
        title = title.strip(_QUOTES).strip()
        title = title.rstrip(".!?:;,").strip()
    return title[:TITLE_MAX_LENGTH].rstrip()


def first_exchange(history: list[Message]) -> tuple[str, str] | None:
    """The first reply and the user message it answered, or None before any reply.

    Paired, not taken separately: a first turn stopped before its reply leaves
    a question with no answer, and the title must not mix two turns.
    """
    for index, message in enumerate(history):
        if message.role == "assistant":
            question = next((m.content for m in reversed(history[:index]) if m.role == "user"), None)
            return (question, message.content) if question else None
    return None


async def generate_title(
    user_text: str,
    reply_text: str,
    model_name: str,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str | None:
    """Ask the model for a title; None if it answers with nothing usable. Model errors propagate.

    Uses a registry client directly: `llm_service` has the chatbot's tools bound,
    and a title request must not come back as a tool call. It runs outside the
    graph, so it carries its own Langfuse config, traced to the conversation.
    """
    llm = LLMRegistry.get(model_name)
    response = await llm.ainvoke(
        [
            SystemMessage(content=TITLE_PROMPT),
            HumanMessage(
                content=f"User: {user_text[:TITLE_INPUT_LIMIT]}\n\nAssistant: {reply_text[:TITLE_INPUT_LIMIT]}"
            ),
        ],
        config=create_graph_config(conversation_id, user_id),
    )
    return clean_title(response.text) or None
