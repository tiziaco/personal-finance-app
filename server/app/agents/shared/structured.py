"""A model call whose answer must be JSON of a known shape: the import's two agents use it."""

import json
import re
from typing import TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.integrations.llm import LLMService

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def structured_llm() -> LLMService:
    """A service of its own for one import's calls.

    Tool-less: the chatbot's `llm_service` has tools bound, and an answer here
    must never be a tool call. Its own: LLMService keeps its fallback model on
    itself, so a shared one would let one import's failures move every other
    import's model. Builds no client until the first call, so it needs no API key.
    """
    return LLMService()


class InvalidModelAnswer(ValueError):
    """The model answered, but not with JSON of the expected shape."""


def parse_answer(text: str, shape: type[T]) -> T:
    """`text` as `shape`, tolerating a Markdown code fence. Raises InvalidModelAnswer."""
    cleaned = _FENCE.sub("", text.strip())
    try:
        return shape.model_validate(json.loads(cleaned))
    except (json.JSONDecodeError, ValidationError) as e:
        raise InvalidModelAnswer(type(e).__name__) from e


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(InvalidModelAnswer),
    reraise=True,
)
async def _ask_once(service: LLMService, messages: list, shape: type[T], config: dict) -> T:
    response = await service.call(messages, config=config)
    return parse_answer(response.text, shape)


async def ask_json(service: LLMService, system: str, user: str, shape: type[T], config: dict) -> T:
    """Ask, parse and validate; an invalid answer is asked once more, then raises InvalidModelAnswer.

    A model error (LLMServiceError) propagates: the service has already retried
    and fallen back through its registry.
    """
    return await _ask_once(service, [SystemMessage(content=system), HumanMessage(content=user)], shape, config)
