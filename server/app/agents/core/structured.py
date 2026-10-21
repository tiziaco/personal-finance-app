"""A model call whose answer must be JSON of a known shape: the one-call agents use it."""

import json
import re
from typing import TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable, RunnableConfig
from openai import OpenAIError
from pydantic import BaseModel, ValidationError

from app.integrations.llm import chat_model, translate_error, with_fallbacks

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")

# The first answer plus one re-ask.
_ATTEMPTS = 2


class InvalidModelAnswer(ValueError):
    """The model answered, but not with JSON of the expected shape."""


def parse_answer(text: str, shape: type[T]) -> T:
    """`text` as `shape`, tolerating a Markdown code fence. Raises InvalidModelAnswer."""
    cleaned = _FENCE.sub("", text.strip())
    try:
        return shape.model_validate(json.loads(cleaned))
    except (json.JSONDecodeError, ValidationError) as e:
        raise InvalidModelAnswer(type(e).__name__) from e


async def ask(shape: type[T], system: str, user: str, config: RunnableConfig, *, model: Runnable | None = None) -> T:
    """Ask, parse and validate; an invalid answer is asked once more, then raises InvalidModelAnswer.

    The default model is the primary with its fallback list behind it; a given `model`
    is used alone. A model error (after the fallbacks) is raised as an LLMServiceError
    and is not asked again. The prompts keep the JSON contract in their text, so the
    model is called plain and the reply parsed here rather than bound to a schema.
    """
    runnable = model if model is not None else with_fallbacks(chat_model())
    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    for attempt in range(1, _ATTEMPTS + 1):
        try:
            response = await runnable.ainvoke(messages, config=config)
        except OpenAIError as e:
            raise translate_error(e) from e
        try:
            return parse_answer(response.text, shape)
        except InvalidModelAnswer:
            if attempt == _ATTEMPTS:
                raise
    raise AssertionError("unreachable")  # pragma: no cover
