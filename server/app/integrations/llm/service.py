"""LLM service for managing LLM calls with retries and fallback mechanisms."""

from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from openai import (
    APIError,
    APITimeoutError,
    OpenAIError,
    RateLimitError,
)
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import (
    Environment,
    settings,
)
from app.core.logging import logger
from app.integrations.llm.exceptions import (
    LLMAPIError,
    LLMFallbackExhaustedError,
    LLMRateLimitError,
    LLMTimeoutError,
)


class LLMRegistry:
    """Registry of available LLM models, built on first use and cached."""

    # Model configuration only — no live clients. Constructing a ChatOpenAI
    # builds an openai.OpenAI (plus an AsyncOpenAI and two httpx clients), and
    # since openai 2.34 that raises on an empty api_key rather than deferring
    # the failure to the first call. Doing it in this class body would make
    # importing this module — and so app.main, and so `make check-contract` —
    # require a real secret, which CI deliberately runs without.
    LLMS: List[Dict[str, Any]] = [
        {"name": "openai/gpt-5-mini", "params": {"reasoning": {"effort": "low"}}},
        {"name": "openai/gpt-5", "params": {"reasoning": {"effort": "medium"}}},
        {"name": "openai/gpt-5-nano", "params": {"reasoning": {"effort": "minimal"}}},
        {
            "name": "openai/gpt-4o",
            "params": {
                "temperature": settings.llm.DEFAULT_LLM_TEMPERATURE,
                "top_p": 0.95 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.8,
                "presence_penalty": 0.1 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.0,
                "frequency_penalty": 0.1 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.0,
            },
        },
        {
            "name": "openai/gpt-4o-mini",
            "params": {
                "temperature": settings.llm.DEFAULT_LLM_TEMPERATURE,
                "top_p": 0.9 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.8,
            },
        },
    ]

    # Clients built by `get()`, keyed by model name. A plain dict is enough:
    # the process is single-threaded asyncio, and a lost race would cost one
    # redundant client, not a correctness bug.
    _instances: Dict[str, BaseChatModel] = {}

    @classmethod
    def _build(cls, model_name: str, **params) -> BaseChatModel:
        """Construct a chat model against OpenRouter. The one site that reads the credential."""
        return ChatOpenAI(
            model=model_name,
            # The OpenRouter id carries a provider prefix; langchain-openai counts tokens by the bare OpenAI name.
            tiktoken_model_name=model_name.rsplit("/", 1)[-1],
            api_key=settings.llm.OPENROUTER_API_KEY.get_secret_value(),
            base_url=settings.llm.LLM_BASE_URL,
            **params,
        )

    @classmethod
    def get(cls, model_name: str, **kwargs) -> BaseChatModel:
        """Get an LLM by name, raising ValueError if it is not registered."""
        model_entry = None
        for entry in cls.LLMS:
            if entry["name"] == model_name:
                model_entry = entry
                break

        if not model_entry:
            available_models = [entry["name"] for entry in cls.LLMS]
            raise ValueError(
                f"model '{model_name}' not found in registry. available models: {', '.join(available_models)}"
            )

        # Overrides replace the entry's configuration rather than layering onto
        # it: only the model and the credential carry over.
        if kwargs:
            logger.debug("creating_llm_with_custom_args", model_name=model_name, custom_args=list(kwargs.keys()))
            return cls._build(model_name, **kwargs)

        if model_name not in cls._instances:
            cls._instances[model_name] = cls._build(
                model_name, max_tokens=settings.llm.MAX_TOKENS, **model_entry["params"]
            )
        logger.debug("using_default_llm_instance", model_name=model_name)
        return cls._instances[model_name]

    @classmethod
    def get_all_names(cls) -> List[str]:
        """Get all registered LLM names, in registry order."""
        return [entry["name"] for entry in cls.LLMS]

    @classmethod
    def get_model_at_index(cls, index: int) -> Dict[str, Any]:
        """Get the model entry at ``index``, or the first one if out of range."""
        if 0 <= index < len(cls.LLMS):
            return cls.LLMS[index]
        return cls.LLMS[0]


class LLMService:
    """Service for managing LLM calls with retries and circular fallback."""

    def __init__(self):
        """Initialize the LLM service.

        No client is constructed here: `llm_service` below is a module-level
        singleton, so anything built in this method runs at import. `get_llm()`
        resolves the client on first use instead.

        `_default_index` is set here and never moves: a call keeps its fallback
        position in its own locals, since `llm_service` is shared by every request.
        """
        self._llm: Optional[BaseChatModel] = None
        self._tools: Optional[List] = None
        self._default_index: int = 0

        all_names = LLMRegistry.get_all_names()
        try:
            self._default_index = all_names.index(settings.llm.DEFAULT_LLM_MODEL)
            logger.info(
                "llm_service_initialized",
                default_model=settings.llm.DEFAULT_LLM_MODEL,
                model_index=self._default_index,
                total_models=len(all_names),
                environment=settings.ENVIRONMENT.value,
            )
        except (ValueError, Exception) as e:
            self._default_index = 0
            logger.warning(
                "default_model_not_found_using_first",
                requested=settings.llm.DEFAULT_LLM_MODEL,
                using=all_names[0] if all_names else "none",
                error=str(e),
            )

    def _resolve(self, model_name: str, **kwargs) -> BaseChatModel:
        """Build the client for `model_name` with the registered tools bound.

        Every assignment to `_llm` must go through here. Tools belong to the
        service, not to whichever client it holds: assigning a bare registry
        client leaves the agent toolless after the first fallback rotation, and
        silently, since the graph routes on `tool_calls` and simply sees none.
        Resolving from the registry rather than from a held client is what makes
        that correct for `_next`, which moves to another model.
        """
        llm = LLMRegistry.get(model_name, **kwargs)
        return llm.bind_tools(self._tools) if self._tools else llm

    def _next(self, index: int) -> tuple[int, BaseChatModel]:
        """The model after `index` in the registry, wrapping to 0 at the end, with its client resolved."""
        next_index = (index + 1) % len(LLMRegistry.LLMS)
        return next_index, self._resolve(LLMRegistry.get_model_at_index(next_index)["name"])

    @retry(
        stop=stop_after_attempt(settings.llm.MAX_LLM_CALL_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
        before_sleep=before_sleep_log(logger, "WARNING"),
        reraise=True,
    )
    async def _call_llm_with_retry(
        self, llm: BaseChatModel, messages: List[BaseMessage], config: Optional[RunnableConfig] = None
    ) -> BaseMessage:
        """Call `llm`, retrying per the decorator. Raises OpenAIError if all fail."""
        try:
            response = await llm.ainvoke(messages, config=config)
            logger.debug("llm_call_successful", message_count=len(messages))
            return response
        except (RateLimitError, APITimeoutError, APIError) as e:
            logger.warning(
                "llm_call_failed_retrying",
                error_type=type(e).__name__,
                error=str(e),
                exc_info=True,
            )
            raise
        except OpenAIError as e:
            logger.error(
                "llm_call_failed",
                error_type=type(e).__name__,
                error=str(e),
            )
            raise

    async def call(
        self,
        messages: List[BaseMessage],
        model_name: Optional[str] = None,
        config: Optional[RunnableConfig] = None,
        **model_kwargs,
    ) -> BaseMessage:
        """Call the LLM with circular fallback, on `model_name` if given.

        `config` carries tracing callbacks for a call made outside a graph;
        inside one, LangChain propagates the graph's.

        Raises:
            ValueError: `model_name` is not in the registry.
            LLMFallbackExhaustedError: Every model failed after retries.
        """
        if not model_name:
            return await self._call_with_fallback(messages, config, self._default_index, self.get_llm())

        try:
            pinned = self._resolve(model_name, **model_kwargs)
        except ValueError as e:
            logger.error("requested_model_not_found", model_name=model_name, error=str(e))
            raise

        # The pin lives in this call's locals, never on the service: `llm_service` is a
        # singleton shared by every request, and a pin set on it would retarget their calls.
        logger.info("using_requested_model", model_name=model_name, has_custom_kwargs=bool(model_kwargs))
        return await self._call_with_fallback(messages, config, LLMRegistry.get_all_names().index(model_name), pinned)

    async def _call_with_fallback(
        self,
        messages: List[BaseMessage],
        config: Optional[RunnableConfig],
        start_index: int,
        start_llm: BaseChatModel,
    ) -> BaseMessage:
        """Call the model at `start_index`, rotating through the registry on failure.

        The position is in locals. Calls run at once on one service, so a position kept
        on the service would be moved by every call's failures, and a call could use up
        its attempts without reaching a healthy model.

        Raises:
            LLMRateLimitError: If every model rate-limits
            LLMTimeoutError: If every model times out
            LLMAPIError: If every model returns an API error
            LLMFallbackExhaustedError: If the rotation ends without a response
        """
        total_models = len(LLMRegistry.LLMS)
        index, llm = start_index, start_llm
        models_tried = 0
        last_error = None

        while models_tried < total_models:
            current_model_name = LLMRegistry.LLMS[index]["name"]
            try:
                return await self._call_llm_with_retry(llm, messages, config)
            except RateLimitError as e:
                last_error = e
                models_tried += 1
                logger.error(
                    "llm_rate_limit_after_retries",
                    model=current_model_name,
                    models_tried=models_tried,
                    total_models=total_models,
                    error=str(e),
                )
                if models_tried >= total_models:
                    raise LLMRateLimitError(
                        f"Rate limit exceeded on all {total_models} models",
                        models_tried=models_tried,
                        last_model=current_model_name,
                    ) from e
            except APITimeoutError as e:
                last_error = e
                models_tried += 1
                logger.error(
                    "llm_timeout_after_retries",
                    model=current_model_name,
                    models_tried=models_tried,
                    total_models=total_models,
                    error=str(e),
                )
                if models_tried >= total_models:
                    raise LLMTimeoutError(
                        f"Timeout on all {total_models} models",
                        models_tried=models_tried,
                        last_model=current_model_name,
                    ) from e
            except OpenAIError as e:
                last_error = e
                models_tried += 1
                logger.error(
                    "llm_call_failed_after_retries",
                    model=current_model_name,
                    models_tried=models_tried,
                    total_models=total_models,
                    error=str(e),
                )
                if models_tried >= total_models:
                    logger.error(
                        "all_models_failed",
                        models_tried=models_tried,
                        starting_model=LLMRegistry.LLMS[start_index]["name"],
                    )
                    raise LLMAPIError(
                        f"LLM API error on all {total_models} models: {str(e)}",
                        models_tried=models_tried,
                        last_model=current_model_name,
                        error_type=type(e).__name__,
                    ) from e

            try:
                next_index, llm = self._next(index)
            except Exception as e:
                logger.error("model_switch_failed", error=str(e))
                break
            logger.warning(
                "switching_to_next_model",
                from_index=index,
                to_index=next_index,
                to_model=LLMRegistry.LLMS[next_index]["name"],
            )
            index = next_index

        # Only reachable when a switch failed mid-rotation; the exhaustion cases
        # above raise their own typed error.
        raise LLMFallbackExhaustedError(
            f"All {total_models} models failed after retries. Last error: {str(last_error)}",
            models_tried=models_tried,
            starting_model=LLMRegistry.LLMS[start_index]["name"],
            last_error=str(last_error) if last_error else None,
        )

    def get_llm(self) -> BaseChatModel:
        """The default model's client, building it on first use."""
        if self._llm is None:
            entry = LLMRegistry.get_model_at_index(self._default_index)
            self._llm = self._resolve(entry["name"])
        return self._llm

    def current_model_name(self) -> str:
        """The default model: where every call that pins none starts.

        Ask here, not the client: `get_name()` returns the class name, and
        `model_name` is absent from a tool-bound client's own attributes.
        """
        return LLMRegistry.get_model_at_index(self._default_index)["name"]

    def bind_tools(self, tools: List) -> "LLMService":
        """Record tools to bind on every client this service resolves.

        Recorded rather than bound here: `_llm` is None until first use, and
        every later model change would have to remember to re-bind. Dropping the
        cached client lets `get_llm()` rebuild through `_resolve`, the one place
        that knows about tools.
        """
        self._tools = tools
        self._llm = None
        logger.debug("tools_bound_to_llm", tool_count=len(tools))
        return self


llm_service = LLMService()
