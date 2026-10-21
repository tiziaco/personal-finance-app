"""Times every model call under the name of the model that answered, and translates provider errors.

Innermost of the model-call hooks, so it sees the provider's reply or error before
anything else does. A fallback can answer instead of the requested model; its name
is on the response and only known after the call, so the duration is observed
rather than timed with a context manager.
"""

import time
from collections.abc import Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langgraph.config import get_config
from openai import OpenAIError

from app.core.config import settings
from app.core.logging import logger
from app.core.metrics import llm_inference_duration_seconds
from app.integrations.llm import translate_error


def _conversation_id() -> str | None:
    """The thread id for log lines; `None` outside a run, so error handling cannot raise."""
    try:
        return get_config()["configurable"]["thread_id"]
    except Exception:
        return None


class ModelTimingMiddleware(AgentMiddleware):
    """Inference duration by answering model, the response log line, and OpenAI error translation."""

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        """Call the model; an `OpenAIError` that escapes it is raised as the service's typed error."""
        started = time.perf_counter()
        try:
            response = await handler(request)
        except OpenAIError as e:
            logger.error(
                "llm_call_failed_all_models",
                conversation_id=_conversation_id(),
                error_type=type(e).__name__,
                error=str(e),
                environment=settings.ENVIRONMENT.value,
            )
            raise translate_error(e) from e

        message = response.result[0]
        answering = message.response_metadata.get("model_name") or getattr(request.model, "model_name", None)
        llm_inference_duration_seconds.labels(model=answering).observe(time.perf_counter() - started)
        logger.info(
            "llm_response_generated",
            model=answering,
            wrap_up=not request.tools,
            environment=settings.ENVIRONMENT.value,
        )
        return response
