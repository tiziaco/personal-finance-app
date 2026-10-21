"""Chat model factory against OpenRouter, the fallback list and the error translation."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from openai import (
    APITimeoutError,
    OpenAIError,
    RateLimitError,
)

from app.core.config import settings
from app.integrations.llm.exceptions import (
    LLMAPIError,
    LLMRateLimitError,
    LLMServiceError,
    LLMTimeoutError,
)

# Stands in for an unset OPENROUTER_API_KEY. Given an empty key, mem0's OpenAI
# client falls back to OPENAI_API_KEY from the environment and would send that
# secret to OpenRouter; and since openai 2.34 constructing a client with an empty
# key raises. With this, a call fails with a 401 that its caller logs, and
# importing the app needs no secret.
PLACEHOLDER_KEY = "openrouter-key-not-set"

# Default reasoning effort per bare model name. A gpt-5 name outside the table gets
# no `reasoning` parameter unless the caller passes an effort.
REASONING_EFFORT_DEFAULTS: dict[str, str] = {"gpt-5-mini": "low", "gpt-5": "medium", "gpt-5-nano": "minimal"}

# Clients by resolved (name, max_tokens, reasoning_effort). A plain dict is enough:
# the process is single-threaded asyncio, and a lost race builds one client twice.
_clients: dict[tuple[str, int, str | None], BaseChatModel] = {}


def _bare(name: str) -> str:
    return name.rsplit("/", 1)[-1]


def is_reasoning_model(name: str) -> bool:
    """Whether the model reasons: its bare name, after the provider prefix, starts with `gpt-5`."""
    return _bare(name).startswith("gpt-5")


def chat_model(
    name: str | None = None,
    *,
    max_tokens: int | None = None,
    reasoning_effort: str | None = None,
) -> BaseChatModel:
    """The client for `name` (default `DEFAULT_LLM_MODEL`), built on first use and cached by its tuning."""
    name = name or settings.llm.DEFAULT_LLM_MODEL
    max_tokens = max_tokens or settings.llm.MAX_TOKENS
    bare = _bare(name)
    effort = (reasoning_effort or REASONING_EFFORT_DEFAULTS.get(bare)) if is_reasoning_model(name) else None
    key = (name, max_tokens, effort)
    if key not in _clients:
        _clients[key] = ChatOpenAI(
            model=name,
            tiktoken_model_name=bare,
            api_key=settings.llm.OPENROUTER_API_KEY.get_secret_value() or PLACEHOLDER_KEY,
            base_url=settings.llm.LLM_BASE_URL,
            max_tokens=max_tokens,
            max_retries=settings.llm.MAX_LLM_CALL_RETRIES,
            reasoning={"effort": effort, "summary": "auto"} if effort else None,
        )
    return _clients[key]


def fallback_models(
    *,
    primary: str | None = None,
    max_tokens: int | None = None,
    reasoning_effort: str | None = None,
) -> list[BaseChatModel]:
    """The `LLM_FALLBACK_MODELS` clients in order, leaving out the primary so it is never tried twice."""
    primary = primary or settings.llm.DEFAULT_LLM_MODEL
    return [
        chat_model(name, max_tokens=max_tokens, reasoning_effort=reasoning_effort)
        for name in settings.llm.LLM_FALLBACK_MODELS
        if name != primary
    ]


def with_fallbacks(
    model: BaseChatModel,
    *,
    max_tokens: int | None = None,
    reasoning_effort: str | None = None,
) -> Runnable:
    """`model` with the fallback list behind it, or `model` itself when there is none.

    Only an OpenAIError moves to the next model, as the old service did: a parse or
    validation failure belongs to the caller.
    """
    fallbacks = fallback_models(primary=model.model_name, max_tokens=max_tokens, reasoning_effort=reasoning_effort)
    if not fallbacks:
        return model
    return model.with_fallbacks(fallbacks, exceptions_to_handle=(OpenAIError,))


def translate_error(error: BaseException) -> LLMServiceError:
    """The service error for a model call that failed: rate limit, timeout, or any other."""
    typed: type[LLMServiceError] = LLMAPIError
    if isinstance(error, RateLimitError):
        typed = LLMRateLimitError
    elif isinstance(error, APITimeoutError):
        typed = LLMTimeoutError
    return typed(f"model call failed with {type(error).__name__}", last_error_type=type(error).__name__)
