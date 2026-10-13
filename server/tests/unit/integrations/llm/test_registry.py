"""Tests for app.integrations.llm.service.LLMRegistry — model resolution and lookup."""

import pytest
from langchain_core.language_models.chat_models import BaseChatModel

from app.integrations.llm.service import LLMRegistry

pytestmark = pytest.mark.unit


class TestLLMRegistryGet:
    """Tests for LLMRegistry.get()."""

    def test_known_model_returns_instance(self):
        llm = LLMRegistry.get("openai/gpt-5-mini")
        assert isinstance(llm, BaseChatModel)

    def test_unknown_model_raises_value_error(self):
        with pytest.raises(ValueError, match="not found in registry"):
            LLMRegistry.get("nonexistent-model")

    def test_unknown_model_error_lists_available(self):
        with pytest.raises(ValueError) as exc_info:
            LLMRegistry.get("fake-model")
        error_msg = str(exc_info.value)
        assert "openai/gpt-5-mini" in error_msg

    def test_default_instance_is_cached(self):
        """The same object comes back on every call.

        Clients are built on first use now, so the cache is what preserves the
        shared-instance behaviour they had when built at import.
        """
        assert LLMRegistry.get("openai/gpt-5-mini") is LLMRegistry.get("openai/gpt-5-mini")

    def test_overrides_get_a_separate_instance(self):
        assert LLMRegistry.get("openai/gpt-5-mini", temperature=0.9) is not LLMRegistry.get("openai/gpt-5-mini")


class TestLLMRegistryGetAllNames:
    """Tests for LLMRegistry.get_all_names()."""

    def test_returns_list_of_strings(self):
        names = LLMRegistry.get_all_names()
        assert isinstance(names, list)
        assert all(isinstance(n, str) for n in names)

    def test_contains_expected_models(self):
        names = LLMRegistry.get_all_names()
        assert "openai/gpt-5-mini" in names
        assert "openai/gpt-5" in names

    def test_order_matches_llms_list(self):
        names = LLMRegistry.get_all_names()
        assert names == [entry["name"] for entry in LLMRegistry.LLMS]


class TestLLMRegistryGetModelAtIndex:
    """Tests for LLMRegistry.get_model_at_index()."""

    def test_valid_index(self):
        entry = LLMRegistry.get_model_at_index(0)
        assert "name" in entry
        assert "params" in entry

    def test_out_of_bounds_wraps_to_first(self):
        entry = LLMRegistry.get_model_at_index(999)
        assert entry == LLMRegistry.LLMS[0]

    def test_negative_index_wraps_to_first(self):
        entry = LLMRegistry.get_model_at_index(-1)
        assert entry == LLMRegistry.LLMS[0]


class TestLLMRegistryProvider:
    """Every client talks to OpenRouter."""

    def test_client_points_at_the_configured_base_url(self):
        from app.core.config import settings

        llm = LLMRegistry.get("openai/gpt-5-mini")
        assert llm.openai_api_base == settings.llm.LLM_BASE_URL

    def test_base_url_defaults_to_openrouter(self):
        from app.core.config import LLMSettings

        assert LLMSettings.model_fields["LLM_BASE_URL"].default == "https://openrouter.ai/api/v1"

    def test_every_registry_name_is_an_openrouter_model_id(self):
        assert all(name.startswith("openai/") for name in LLMRegistry.get_all_names())
