"""Tests for app.integrations.llm.models — the client factory, fallback list and error translation."""

from unittest.mock import MagicMock

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from openai import APIError, APITimeoutError, RateLimitError
from pydantic import SecretStr

from app.core.config import LLMSettings, settings
from app.integrations.llm import models
from app.integrations.llm.exceptions import LLMAPIError, LLMRateLimitError, LLMTimeoutError
from app.integrations.llm.models import (
    PLACEHOLDER_KEY,
    chat_model,
    fallback_models,
    translate_error,
    with_fallbacks,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def fresh_clients(monkeypatch):
    """Every test builds from its own settings: no client cached under another test's."""
    monkeypatch.setattr(models, "_clients", {})


def test_a_gpt5_name_reasons_at_its_table_effort_and_asks_for_summaries():
    m = chat_model("openai/gpt-5-mini")
    assert m.reasoning == {"effort": "low", "summary": "auto"} and m.model_name == "openai/gpt-5-mini"
    assert m.tiktoken_model_name == "gpt-5-mini" and m.max_retries == settings.llm.MAX_LLM_CALL_RETRIES


def test_the_chat_passes_its_own_effort_and_budget():
    m = chat_model("openai/gpt-5-mini", max_tokens=8000, reasoning_effort="high")
    assert m.reasoning["effort"] == "high" and m.max_tokens == 8000


def test_a_non_reasoning_name_gets_no_reasoning_parameters():
    m = chat_model("openai/gpt-4o-mini", reasoning_effort="high")
    assert m.reasoning is None and m.model_name == "openai/gpt-4o-mini"


def test_a_reasoning_name_outside_the_table_gets_no_reasoning_parameter():
    assert chat_model("openai/gpt-5-pro").reasoning is None


def test_same_arguments_share_one_client_and_different_tuning_does_not():
    assert chat_model() is chat_model() and chat_model(max_tokens=10) is not chat_model()


def test_without_a_key_the_client_still_builds(monkeypatch):
    monkeypatch.setattr(settings.llm, "OPENROUTER_API_KEY", SecretStr(""))
    assert chat_model().openai_api_key.get_secret_value() == PLACEHOLDER_KEY


def test_fallbacks_follow_the_setting_and_skip_the_primary(monkeypatch):
    monkeypatch.setattr(
        settings.llm, "LLM_FALLBACK_MODELS", [settings.llm.DEFAULT_LLM_MODEL, "openai/gpt-5", "openai/gpt-5-nano"]
    )
    assert [m.model_name for m in fallback_models()] == ["openai/gpt-5", "openai/gpt-5-nano"]


def test_an_empty_fallback_list_returns_the_model_itself(monkeypatch):
    monkeypatch.setattr(settings.llm, "LLM_FALLBACK_MODELS", [])
    m = chat_model()
    assert with_fallbacks(m) is m


def test_a_fallback_list_naming_only_the_primary_returns_the_model_itself(monkeypatch):
    monkeypatch.setattr(settings.llm, "LLM_FALLBACK_MODELS", [settings.llm.DEFAULT_LLM_MODEL])
    m = chat_model()
    assert with_fallbacks(m) is m


def test_with_fallbacks_wraps_in_order(monkeypatch):
    monkeypatch.setattr(settings.llm, "LLM_FALLBACK_MODELS", ["openai/gpt-5", "openai/gpt-5-nano"])
    wrapped = with_fallbacks(chat_model("openai/gpt-5-mini"))
    assert [f.model_name for f in wrapped.fallbacks] == ["openai/gpt-5", "openai/gpt-5-nano"]


async def test_only_an_openai_error_moves_to_the_next_model(monkeypatch):
    """A parse or validation failure from the primary reaches the caller instead of a fallback."""
    monkeypatch.setattr(settings.llm, "LLM_FALLBACK_MODELS", ["openai/gpt-5"])
    wrapped = with_fallbacks(chat_model("openai/gpt-5-mini"))
    assert wrapped.exceptions_to_handle[0].__name__ == "OpenAIError" and len(wrapped.exceptions_to_handle) == 1

    class Primary(GenericFakeChatModel):
        model_name: str = "openai/gpt-5-mini"

        def _generate(self, *args, **kwargs):
            raise ValueError("not an openai error")

    fallback = GenericFakeChatModel(messages=iter([AIMessage(content="fallback")]))
    guarded = Primary(messages=iter([])).with_fallbacks([fallback], exceptions_to_handle=wrapped.exceptions_to_handle)
    with pytest.raises(ValueError):
        await guarded.ainvoke("hi")


def test_the_fallback_list_parses_from_a_json_env_value(monkeypatch):
    monkeypatch.setenv("LLM_FALLBACK_MODELS", '["openai/gpt-5","openai/gpt-5-nano"]')
    monkeypatch.setenv("CHAT_SUMMARY_MODEL", "openai/gpt-5-nano")
    llm = LLMSettings()
    assert llm.LLM_FALLBACK_MODELS == ["openai/gpt-5", "openai/gpt-5-nano"]
    assert llm.CHAT_SUMMARY_MODEL == "openai/gpt-5-nano"


def _rate_limit():
    return RateLimitError(message="limited", response=MagicMock(status_code=429, headers={}), body=None)


@pytest.mark.parametrize(
    "raw, typed",
    [
        (_rate_limit(), LLMRateLimitError),
        (APITimeoutError(request=MagicMock()), LLMTimeoutError),
        (APIError(message="server error", request=MagicMock(), body=None), LLMAPIError),
        (ValueError("boom"), LLMAPIError),
    ],
)
def test_translate_error_follows_the_failure(raw, typed):
    error = translate_error(raw)
    assert type(error) is typed
    assert error.message == f"model call failed with {type(raw).__name__}"
    assert error.context == {"last_error_type": type(raw).__name__}
