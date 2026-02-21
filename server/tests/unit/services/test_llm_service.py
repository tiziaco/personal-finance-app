"""Tests for app.services.llm.service.LLMService — retry logic and fallback chain."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from openai import APIError, APITimeoutError, RateLimitError

from app.services.llm.exceptions import (
    LLMAPIError,
    LLMFallbackExhaustedError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.services.llm.service import LLMRegistry, LLMService

pytestmark = pytest.mark.unit


@pytest.fixture
def messages():
    return [HumanMessage(content="Hello")]


class TestLLMServiceInit:
    """Tests for LLMService initialization."""

    def test_default_model_found(self):
        service = LLMService()
        assert service._llm is not None

    def test_get_llm_returns_instance(self):
        service = LLMService()
        assert service.get_llm() is not None


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

        async def mock_retry(msgs):
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

        async def always_rate_limit(msgs):
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

        async def always_timeout(msgs):
            raise APITimeoutError(request=MagicMock())

        with patch.object(service, "_call_llm_with_retry", side_effect=always_timeout):
            with pytest.raises(LLMTimeoutError):
                await service.call(messages)

    @pytest.mark.asyncio
    async def test_all_models_api_error_raises(self, messages):
        service = LLMService()

        async def always_api_error(msgs):
            raise APIError(
                message="server error",
                request=MagicMock(),
                body=None,
            )

        with patch.object(service, "_call_llm_with_retry", side_effect=always_api_error):
            with pytest.raises(LLMAPIError):
                await service.call(messages)


class TestLLMServiceModelSwitching:
    """Tests for circular model switching."""

    def test_next_model_index_wraps(self):
        service = LLMService()
        total = len(LLMRegistry.LLMS)
        service._current_model_index = total - 1

        next_idx = service._get_next_model_index()
        assert next_idx == 0

    def test_switch_to_next_model(self):
        service = LLMService()
        original_index = service._current_model_index

        success = service._switch_to_next_model()

        assert success is True
        assert service._current_model_index != original_index
