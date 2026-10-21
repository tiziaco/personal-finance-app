"""Tests for app.agents.chatbot.middleware.model_timing — inference timing, the response log and error translation."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest
from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from openai import RateLimitError
from prometheus_client import REGISTRY

from app.agents.chatbot.middleware.model_timing import ModelTimingMiddleware
from app.integrations.llm import LLMRateLimitError

pytestmark = pytest.mark.unit

MODULE = "app.agents.chatbot.middleware.model_timing"


def _request(*, tools=None, model_name: str | None = "requested-model") -> ModelRequest:
    model = SimpleNamespace(model_name=model_name) if model_name else SimpleNamespace()
    return ModelRequest(
        model=model,
        messages=[HumanMessage(content="q")],
        system_message=SystemMessage("sys"),
        tool_choice=None,
        tools=[MagicMock()] if tools is None else tools,
        response_format=None,
        state={"messages": []},
        runtime=SimpleNamespace(),
        model_settings={},
    )


def _observed(model: str) -> int:
    return int(REGISTRY.get_sample_value("llm_inference_duration_seconds_count", {"model": model}) or 0)


def _handler(reply: AIMessage):
    async def handler(request):
        return ModelResponse(result=[reply])

    return handler


async def test_timing_labels_the_answering_model_from_the_response_metadata():
    reply = AIMessage(content="hi", response_metadata={"model_name": "answering-model"})
    before = _observed("answering-model")

    with patch(f"{MODULE}.logger") as log:
        response = await ModelTimingMiddleware().awrap_model_call(_request(), _handler(reply))

    assert response.result == [reply]
    assert _observed("answering-model") == before + 1
    kwargs = log.info.call_args.kwargs
    assert log.info.call_args.args[0] == "llm_response_generated"
    assert kwargs["model"] == "answering-model" and kwargs["wrap_up"] is False and "environment" in kwargs


async def test_timing_falls_back_to_the_requested_model_name():
    before = _observed("requested-model")

    await ModelTimingMiddleware().awrap_model_call(_request(), _handler(AIMessage(content="hi")))

    assert _observed("requested-model") == before + 1


async def test_a_wrap_up_call_without_tools_is_logged_as_such():
    with patch(f"{MODULE}.logger") as log:
        await ModelTimingMiddleware().awrap_model_call(_request(tools=[]), _handler(AIMessage(content="hi")))

    assert log.info.call_args.kwargs["wrap_up"] is True


async def test_a_provider_error_is_translated():
    response = httpx.Response(429, request=httpx.Request("POST", "https://x"))

    async def handler(request):
        raise RateLimitError("slow down", response=response, body=None)

    with patch(f"{MODULE}.get_config", return_value={"configurable": {"thread_id": "thread-1"}}):
        with patch(f"{MODULE}.logger") as log:
            with pytest.raises(LLMRateLimitError):
                await ModelTimingMiddleware().awrap_model_call(_request(), handler)

    assert log.error.call_args.args[0] == "llm_call_failed_all_models"
    assert log.error.call_args.kwargs["conversation_id"] == "thread-1"


async def test_other_errors_pass_through_untranslated():
    async def handler(request):
        raise ValueError("not a provider error")

    with pytest.raises(ValueError):
        await ModelTimingMiddleware().awrap_model_call(_request(), handler)
