"""A short title for a conversation, written by the model from its first exchange."""

import re

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from app.agents.graph import process_llm_response
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
    title = re.sub(r"^title:\s*", "", title, flags=re.IGNORECASE)
    title = title.strip(_QUOTES).strip()
    title = title.rstrip(".!?:;,").strip()
    return title[:TITLE_MAX_LENGTH].rstrip()


async def generate_title(user_text: str, reply_text: str, model_name: str) -> str:
    """Ask the model for a title. Raises ValueError on an empty one; model errors propagate.

    Uses a registry client directly: `llm_service` has the chatbot's tools bound,
    and a title request must not come back as a tool call.
    """
    llm = LLMRegistry.get(model_name)
    response = await llm.ainvoke(
        [
            SystemMessage(content=TITLE_PROMPT),
            HumanMessage(
                content=f"User: {user_text[:TITLE_INPUT_LIMIT]}\n\nAssistant: {reply_text[:TITLE_INPUT_LIMIT]}"
            ),
        ]
    )
    title = clean_title(str(process_llm_response(response).content))
    if not title:
        raise ValueError("the model returned an empty title")
    return title
