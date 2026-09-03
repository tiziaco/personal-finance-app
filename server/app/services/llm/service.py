"""LLM service for managing LLM calls with retries and fallback mechanisms."""

from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
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
from app.services.llm.exceptions import (
    LLMAPIError,
    LLMFallbackExhaustedError,
    LLMRateLimitError,
    LLMTimeoutError,
)


class LLMRegistry:
    """Registry of available LLM models, built on first use and cached.

    This class maintains a list of LLM configurations and provides
    methods to retrieve them by name with optional argument overrides.
    """

    # Model configuration only — no live clients. Constructing a ChatOpenAI
    # builds an openai.OpenAI (plus an AsyncOpenAI and two httpx clients), and
    # since openai 2.34 that raises on an empty api_key rather than deferring
    # the failure to the first call. Doing it in this class body would make
    # importing this module — and so app.main, and so `make check-contract` —
    # require a real secret, which CI deliberately runs without.
    LLMS: List[Dict[str, Any]] = [
        {"name": "gpt-5-mini", "params": {"reasoning": {"effort": "low"}}},
        {"name": "gpt-5", "params": {"reasoning": {"effort": "medium"}}},
        {"name": "gpt-5-nano", "params": {"reasoning": {"effort": "minimal"}}},
        {
            "name": "gpt-4o",
            "params": {
                "temperature": settings.llm.DEFAULT_LLM_TEMPERATURE,
                "top_p": 0.95 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.8,
                "presence_penalty": 0.1 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.0,
                "frequency_penalty": 0.1 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.0,
            },
        },
        {
            "name": "gpt-4o-mini",
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
        """Construct a chat model. The one site that reads the credential.

        Args:
            model_name: Model to construct
            **params: Model arguments

        Returns:
            A new BaseChatModel instance
        """
        return ChatOpenAI(
            model=model_name,
            api_key=settings.llm.OPENAI_API_KEY.get_secret_value(),
            **params,
        )

    @classmethod
    def get(cls, model_name: str, **kwargs) -> BaseChatModel:
        """Get an LLM by name with optional argument overrides.

        Args:
            model_name: Name of the model to retrieve
            **kwargs: Optional arguments to override default model configuration

        Returns:
            BaseChatModel instance

        Raises:
            ValueError: If model_name is not found in LLMS
        """
        # Find the model in the registry
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

        # If user provides kwargs, create a new instance with those args.
        # As before, overrides replace the entry's configuration rather than
        # layering onto it — only the model and credential carry over.
        if kwargs:
            logger.debug("creating_llm_with_custom_args", model_name=model_name, custom_args=list(kwargs.keys()))
            return cls._build(model_name, **kwargs)

        # Return the default instance, building it the first time it is asked for
        if model_name not in cls._instances:
            cls._instances[model_name] = cls._build(
                model_name, max_tokens=settings.llm.MAX_TOKENS, **model_entry["params"]
            )
        logger.debug("using_default_llm_instance", model_name=model_name)
        return cls._instances[model_name]

    @classmethod
    def get_all_names(cls) -> List[str]:
        """Get all registered LLM names in order.

        Returns:
            List of LLM names
        """
        return [entry["name"] for entry in cls.LLMS]

    @classmethod
    def get_model_at_index(cls, index: int) -> Dict[str, Any]:
        """Get model entry at specific index.

        Args:
            index: Index of the model in LLMS list

        Returns:
            Model entry dict
        """
        if 0 <= index < len(cls.LLMS):
            return cls.LLMS[index]
        return cls.LLMS[0]  # Wrap around to first model


class LLMService:
    """Service for managing LLM calls with retries and circular fallback.

    This service handles all LLM interactions with automatic retry logic,
    rate limit handling, and circular fallback through all available models.
    """

    def __init__(self):
        """Initialize the LLM service.

        No client is constructed here. `llm_service` below is a module-level
        singleton, so anything built in this method runs at import; `get_llm()`
        resolves the client on first use instead.
        """
        self._llm: Optional[BaseChatModel] = None
        self._tools: Optional[List] = None
        self._current_model_index: int = 0

        # Find index of default model in registry
        all_names = LLMRegistry.get_all_names()
        try:
            self._current_model_index = all_names.index(settings.llm.DEFAULT_LLM_MODEL)
            logger.info(
                "llm_service_initialized",
                default_model=settings.llm.DEFAULT_LLM_MODEL,
                model_index=self._current_model_index,
                total_models=len(all_names),
                environment=settings.ENVIRONMENT.value,
            )
        except (ValueError, Exception) as e:
            # Default model not found, use first model
            self._current_model_index = 0
            logger.warning(
                "default_model_not_found_using_first",
                requested=settings.llm.DEFAULT_LLM_MODEL,
                using=all_names[0] if all_names else "none",
                error=str(e),
            )

    def _resolve(self, model_name: str, **kwargs) -> BaseChatModel:
        """Build the client for `model_name` with the registered tools bound.

        Every assignment to `_llm` goes through here. What is bound is a
        property of the service, not of the particular client it happens to be
        holding: `_switch_to_next_model` and `call(model_name=...)` both used to
        overwrite `_llm` with a bare registry client, and since ChatbotAgent
        binds once at construction and never re-binds, the first fallback
        rotation left the agent toolless for the rest of the process. It did not
        raise — the graph routes on `tool_calls`, which was simply always empty.

        Resolving from the registry rather than from `self._llm` is what makes
        this correct for a *switch*: binding onto the current client would bind
        onto the model we are leaving.

        Args:
            model_name: Model to resolve
            **kwargs: Optional arguments overriding the registry configuration

        Returns:
            A client for `model_name`, tool-bound if `bind_tools` was called
        """
        llm = LLMRegistry.get(model_name, **kwargs)
        return llm.bind_tools(self._tools) if self._tools else llm

    def _get_next_model_index(self) -> int:
        """Get the next model index in circular fashion.

        Returns:
            Next model index (wraps around to 0 if at end)
        """
        total_models = len(LLMRegistry.LLMS)
        next_index = (self._current_model_index + 1) % total_models
        return next_index

    def _switch_to_next_model(self) -> bool:
        """Switch to the next model in the registry (circular).

        Returns:
            True if successfully switched, False otherwise
        """
        try:
            next_index = self._get_next_model_index()
            next_model_entry = LLMRegistry.get_model_at_index(next_index)

            logger.warning(
                "switching_to_next_model",
                from_index=self._current_model_index,
                to_index=next_index,
                to_model=next_model_entry["name"],
            )

            self._current_model_index = next_index
            self._llm = self._resolve(next_model_entry["name"])

            logger.info("model_switched", new_model=next_model_entry["name"], new_index=next_index)
            return True
        except Exception as e:
            logger.error("model_switch_failed", error=str(e))
            return False

    @retry(
        stop=stop_after_attempt(settings.llm.MAX_LLM_CALL_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
        before_sleep=before_sleep_log(logger, "WARNING"),
        reraise=True,
    )
    async def _call_llm_with_retry(self, messages: List[BaseMessage]) -> BaseMessage:
        """Call the LLM with automatic retry logic.

        Args:
            messages: List of messages to send to the LLM

        Returns:
            BaseMessage response from the LLM

        Raises:
            OpenAIError: If all retries fail
        """
        llm = self.get_llm()
        if not llm:
            raise RuntimeError("llm not initialized")

        try:
            response = await llm.ainvoke(messages)
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
        **model_kwargs,
    ) -> BaseMessage:
        """Call the LLM with the specified messages and circular fallback.

        Args:
            messages: List of messages to send to the LLM
            model_name: Optional specific model to use for this call only. If
                None, uses the current model.
            **model_kwargs: Optional kwargs to override default model configuration

        Returns:
            BaseMessage response from the LLM

        Raises:
            ValueError: If `model_name` is not in the registry
            LLMFallbackExhaustedError: If all models fail after retries
        """
        if not model_name:
            return await self._call_with_fallback(messages)

        # Resolved before anything is saved or assigned, so an unknown model
        # raises without having touched the service's state.
        try:
            pinned = self._resolve(model_name, **model_kwargs)
        except ValueError as e:
            logger.error("requested_model_not_found", model_name=model_name, error=str(e))
            raise

        # Pinned for the duration of this call only. `llm_service` is a
        # module-level singleton shared by every request, so an override left in
        # place would retarget everyone else's traffic until the process
        # restarted. The restore also discards any fallback rotation that
        # happened inside the pinned call, which is the same rule applied
        # consistently: the pin was scoped, so its consequences are too.
        saved_llm, saved_index = self._llm, self._current_model_index
        self._llm = pinned
        all_names = LLMRegistry.get_all_names()
        if model_name in all_names:
            self._current_model_index = all_names.index(model_name)
        logger.info("using_requested_model", model_name=model_name, has_custom_kwargs=bool(model_kwargs))

        try:
            return await self._call_with_fallback(messages)
        finally:
            self._llm, self._current_model_index = saved_llm, saved_index

    async def _call_with_fallback(self, messages: List[BaseMessage]) -> BaseMessage:
        """Call the current model, rotating through the registry on failure.

        Args:
            messages: List of messages to send to the LLM

        Returns:
            BaseMessage response from the LLM

        Raises:
            LLMRateLimitError: If every model rate-limits
            LLMTimeoutError: If every model times out
            LLMAPIError: If every model returns an API error
            LLMFallbackExhaustedError: If the rotation ends without a response
        """
        # Track which models we've tried to prevent infinite loops
        total_models = len(LLMRegistry.LLMS)
        models_tried = 0
        starting_index = self._current_model_index
        last_error = None

        while models_tried < total_models:
            try:
                response = await self._call_llm_with_retry(messages)
                return response
            except RateLimitError as e:
                # Translate rate limit errors after retries exhausted
                last_error = e
                models_tried += 1
                current_model_name = LLMRegistry.LLMS[self._current_model_index]["name"]
                
                logger.error(
                    "llm_rate_limit_after_retries",
                    model=current_model_name,
                    models_tried=models_tried,
                    total_models=total_models,
                    error=str(e),
                )
                
                # If we've tried all models, raise domain exception
                if models_tried >= total_models:
                    raise LLMRateLimitError(
                        f"Rate limit exceeded on all {total_models} models",
                        models_tried=models_tried,
                        last_model=current_model_name
                    ) from e
                
                # Switch to next model
                if not self._switch_to_next_model():
                    break
                    
            except APITimeoutError as e:
                # Translate timeout errors after retries exhausted
                last_error = e
                models_tried += 1
                current_model_name = LLMRegistry.LLMS[self._current_model_index]["name"]
                
                logger.error(
                    "llm_timeout_after_retries",
                    model=current_model_name,
                    models_tried=models_tried,
                    total_models=total_models,
                    error=str(e),
                )
                
                # If we've tried all models, raise domain exception
                if models_tried >= total_models:
                    raise LLMTimeoutError(
                        f"Timeout on all {total_models} models",
                        models_tried=models_tried,
                        last_model=current_model_name
                    ) from e
                
                # Switch to next model
                if not self._switch_to_next_model():
                    break
                    
            except OpenAIError as e:
                # Generic OpenAI errors
                last_error = e
                models_tried += 1

                current_model_name = LLMRegistry.LLMS[self._current_model_index]["name"]
                logger.error(
                    "llm_call_failed_after_retries",
                    model=current_model_name,
                    models_tried=models_tried,
                    total_models=total_models,
                    error=str(e),
                )

                # If we've tried all models, raise domain exception
                if models_tried >= total_models:
                    logger.error(
                        "all_models_failed",
                        models_tried=models_tried,
                        starting_model=LLMRegistry.LLMS[starting_index]["name"],
                    )
                    raise LLMAPIError(
                        f"LLM API error on all {total_models} models: {str(e)}",
                        models_tried=models_tried,
                        last_model=current_model_name,
                        error_type=type(e).__name__
                    ) from e

                # Switch to next model in circular fashion
                if not self._switch_to_next_model():
                    logger.error("failed_to_switch_to_next_model")
                    break

                # Continue loop to try next model

        # All models failed - shouldn't reach here but just in case
        raise LLMFallbackExhaustedError(
            f"All {total_models} models failed after retries. Last error: {str(last_error)}",
            models_tried=models_tried,
            starting_model=LLMRegistry.LLMS[starting_index]["name"],
            last_error=str(last_error) if last_error else None
        )

    def get_llm(self) -> Optional[BaseChatModel]:
        """Get the current LLM instance, building it on first use.

        Returns:
            Current BaseChatModel instance or None if not initialized
        """
        if self._llm is None:
            entry = LLMRegistry.get_model_at_index(self._current_model_index)
            self._llm = self._resolve(entry["name"])
        return self._llm

    def current_model_name(self) -> str:
        """The model this service is currently pointed at.

        The single answer to "which model are we on". Asking the client instead
        gives two wrong ones: `get_name()` returns the class name, and
        `model_name` is absent from a tool-bound client's own attributes.

        Returns:
            The registry name of the current model
        """
        return LLMRegistry.get_model_at_index(self._current_model_index)["name"]

    def bind_tools(self, tools: List) -> "LLMService":
        """Bind tools to the current LLM.

        Args:
            tools: List of tools to bind

        Returns:
            Self for method chaining
        """
        # Record the tools rather than binding them onto whatever client is
        # currently held: `_llm` is None until first use, so binding here would
        # have to resolve one first, and every later model change would have to
        # remember to re-bind. Dropping the cached client instead lets
        # `get_llm()` rebuild through `_resolve`, which is the one place that
        # knows about tools.
        self._tools = tools
        self._llm = None
        logger.debug("tools_bound_to_llm", tool_count=len(tools))
        return self


# Create global LLM service instance
llm_service = LLMService()
