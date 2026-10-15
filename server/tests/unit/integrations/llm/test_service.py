"""Tests for app.integrations.llm.service.LLMService — retry logic and fallback chain."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableBinding
from langchain_core.tools import tool
from openai import APIError, APITimeoutError, OpenAIError, RateLimitError

from app.core.config import settings
from app.integrations.llm.exceptions import (
    LLMAPIError,
    LLMFallbackExhaustedError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.integrations.llm.service import LLMRegistry, LLMService

pytestmark = pytest.mark.unit


@pytest.fixture
def messages():
    return [HumanMessage(content="Hello")]


@tool
def echo(text: str) -> str:
    """Echo the input."""
    return text


def _bound_tool_names(llm) -> list[str]:
    return [t["function"]["name"] for t in llm.kwargs["tools"]]


def _other_model(service: LLMService) -> str:
    """A registry model that is not the one `service` is currently on."""
    names = LLMRegistry.get_all_names()
    return names[(service._default_index + 1) % len(names)]


class TestLLMServiceInit:
    """Tests for LLMService initialization."""

    def test_default_model_found(self):
        service = LLMService()
        assert LLMRegistry.get_all_names()[service._default_index] == settings.llm.DEFAULT_LLM_MODEL

    def test_no_client_is_built_until_asked_for(self):
        """__init__ must not construct a client.

        It runs at import via the module-level `llm_service` singleton, and
        constructing a client is what requires a credential.
        """
        service = LLMService()
        assert service._llm is None

    def test_get_llm_returns_instance(self):
        service = LLMService()
        assert service.get_llm() is not None

    def test_bind_tools_binds_after_lazy_resolution(self):
        """bind_tools must resolve the client before binding.

        `_llm` is None until something asks for it, so a bare `if self._llm:`
        guard would bind nothing — leaving ChatbotAgent, which calls this once
        at construction, without its tools.
        """
        bound = LLMService().bind_tools([echo]).get_llm()
        assert isinstance(bound, RunnableBinding)


class TestLLMServiceCall:
    """Tests for LLMService.call() — success and fallback scenarios."""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self, messages):
        service = LLMService()
        expected = AIMessage(content="Hello back!")

        with patch.object(service, "_call_llm_with_retry", new_callable=AsyncMock, return_value=expected):
            result = await service.call(messages)

        assert result.content == "Hello back!"

    @pytest.mark.asyncio
    async def test_fallback_after_rate_limit(self, messages):
        service = LLMService()
        expected = AIMessage(content="Fallback response")

        call_count = 0

        async def mock_retry(llm, msgs, config=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError(
                    message="rate limited",
                    response=MagicMock(status_code=429, headers={}),
                    body=None,
                )
            return expected

        with patch.object(service, "_call_llm_with_retry", side_effect=mock_retry):
            result = await service.call(messages)

        assert result.content == "Fallback response"
        assert call_count == 2  # Tried 2 models

    @pytest.mark.asyncio
    async def test_all_models_rate_limited_raises(self, messages):
        service = LLMService()

        async def always_rate_limit(llm, msgs, config=None):
            raise RateLimitError(
                message="rate limited",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            )

        with patch.object(service, "_call_llm_with_retry", side_effect=always_rate_limit):
            with pytest.raises(LLMRateLimitError):
                await service.call(messages)

    @pytest.mark.asyncio
    async def test_all_models_timeout_raises(self, messages):
        service = LLMService()

        async def always_timeout(llm, msgs, config=None):
            raise APITimeoutError(request=MagicMock())

        with patch.object(service, "_call_llm_with_retry", side_effect=always_timeout):
            with pytest.raises(LLMTimeoutError):
                await service.call(messages)

    @pytest.mark.asyncio
    async def test_all_models_api_error_raises(self, messages):
        service = LLMService()

        async def always_api_error(llm, msgs, config=None):
            raise APIError(
                message="server error",
                request=MagicMock(),
                body=None,
            )

        with patch.object(service, "_call_llm_with_retry", side_effect=always_api_error):
            with pytest.raises(LLMAPIError):
                await service.call(messages)

    @pytest.mark.asyncio
    async def test_pinned_model_keeps_tools(self, messages):
        """A `model_name=` override must resolve a client with the tools bound."""
        service = LLMService().bind_tools([echo])
        seen = {}

        async def capture(llm, msgs, config=None):
            seen["llm"] = llm
            return AIMessage(content="ok")

        with patch.object(service, "_call_llm_with_retry", side_effect=capture):
            await service.call(messages, model_name=_other_model(service))

        assert isinstance(seen["llm"], RunnableBinding)
        assert _bound_tool_names(seen["llm"]) == ["echo"]

    @pytest.mark.asyncio
    async def test_pinned_model_does_not_persist(self, messages):
        """A pinned model applies to its own call and no others.

        `llm_service` is a module-level singleton shared by every request, so an
        override left in place would retarget all subsequent traffic until the
        process restarted.
        """
        service = LLMService()
        before_llm, before_index = service.get_llm(), service._default_index

        with patch.object(
            service, "_call_llm_with_retry", new_callable=AsyncMock, return_value=AIMessage(content="ok")
        ):
            await service.call(messages, model_name=_other_model(service))

        assert service._llm is before_llm
        assert service._default_index == before_index

    @pytest.mark.asyncio
    async def test_pinned_model_restored_when_the_call_raises(self, messages):
        """The pin is a local of the call, so an escaping error has nothing on the service to leave behind.

        A `RuntimeError` escapes `call()` mid-flight without going through the fallback ladder.
        """
        service = LLMService()
        before_llm, before_index = service.get_llm(), service._default_index

        async def boom(llm, msgs, config=None):
            raise RuntimeError("llm not initialized")

        with patch.object(service, "_call_llm_with_retry", side_effect=boom):
            with pytest.raises(RuntimeError):
                await service.call(messages, model_name=_other_model(service))

        assert service._llm is before_llm
        assert service._default_index == before_index


class TestLLMServiceNextModel:
    """Tests for `_next`, the step of the fallback rotation."""

    def test_next_wraps_to_the_first_model(self):
        index, _ = LLMService()._next(len(LLMRegistry.LLMS) - 1)
        assert index == 0

    def test_next_keeps_bound_tools(self):
        """A fallback must not drop the tools.

        The client for the next model is resolved through `_resolve`, which binds the
        service's tools. A bare registry client would leave the agent toolless after a
        fallback, and silently, since the graph routes on an empty `tool_calls` rather
        than raising.
        """
        _, llm = LLMService().bind_tools([echo])._next(0)
        assert isinstance(llm, RunnableBinding)
        assert _bound_tool_names(llm) == ["echo"]


@pytest.mark.asyncio
async def test_call_passes_the_config_to_the_model(messages):
    service = LLMService()
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="ok"))
    service._llm = llm
    config = {"callbacks": [], "metadata": {"langfuse_user_id": "u"}}

    await service.call(messages, config=config)

    llm.ainvoke.assert_awaited_once_with(messages, config=config)


class _FakeModel:
    """A model client that records which call reached it, yields, then answers or fails.

    It fails with a bare OpenAIError, which tenacity does not retry, so a call moves
    to the next model at once and the tests need no waits.
    """

    def __init__(self, name: str, log: list, healthy: bool):
        self.name, self.log, self.healthy = name, log, healthy
        self.hold: asyncio.Event | None = None

    async def ainvoke(self, messages, config=None):
        self.log.append((messages[0].content, self.name))
        await asyncio.sleep(0)
        if self.hold is not None:
            await self.hold.wait()
        if not self.healthy:
            raise OpenAIError(f"{self.name} is down")
        return AIMessage(content=self.name)


class TestConcurrentCalls:
    """Calls running at once on one service: `llm_service` is shared by every request."""

    @pytest.mark.asyncio
    async def test_each_call_walks_the_registry_from_the_default(self):
        names = LLMRegistry.get_all_names()
        service = LLMService()
        start = names.index(service.current_model_name())
        order = [names[(start + i) % len(names)] for i in range(len(names))]
        log: list = []
        fakes = {n: _FakeModel(n, log, healthy=n == order[-1]) for n in names}

        with patch.object(service, "_resolve", side_effect=lambda name, **kw: fakes[name]):
            answers = await asyncio.gather(
                *(service.call([HumanMessage(content=f"call {i}")]) for i in range(3)),
                return_exceptions=True,
            )

        assert [a.content if isinstance(a, AIMessage) else repr(a) for a in answers] == [order[-1]] * 3
        for i in range(3):
            assert [model for caller, model in log if caller == f"call {i}"] == order
        assert service.current_model_name() == order[0]

    @pytest.mark.asyncio
    async def test_a_pinned_call_does_not_move_a_concurrent_default_call(self):
        names = LLMRegistry.get_all_names()
        service = LLMService()
        default = service.current_model_name()
        pinned = next(n for n in names if n != default)
        log: list = []
        fakes = {n: _FakeModel(n, log, healthy=True) for n in names}
        fakes[pinned].hold = asyncio.Event()

        with patch.object(service, "_resolve", side_effect=lambda name, **kw: fakes[name]):
            pinned_call = asyncio.create_task(service.call([HumanMessage(content="pinned")], model_name=pinned))
            while not log:  # the pinned call is at its model, mid-flight
                await asyncio.sleep(0)
            default_answer = await service.call([HumanMessage(content="default")])
            fakes[pinned].hold.set()
            pinned_answer = await pinned_call

        assert default_answer.content == default
        assert pinned_answer.content == pinned
