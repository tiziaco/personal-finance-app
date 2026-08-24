"""Tests for app.services.llm.service.LLMRegistry — model resolution and lookup."""

import pytest
from langchain_core.language_models.chat_models import BaseChatModel

from app.services.llm.service import LLMRegistry

pytestmark = pytest.mark.unit


class TestLLMRegistryGet:
    """Tests for LLMRegistry.get()."""

    def test_known_model_returns_instance(self):
        llm = LLMRegistry.get("gpt-5-mini")
        assert isinstance(llm, BaseChatModel)

    def test_unknown_model_raises_value_error(self):
        with pytest.raises(ValueError, match="not found in registry"):
            LLMRegistry.get("nonexistent-model")

    def test_unknown_model_error_lists_available(self):
        with pytest.raises(ValueError) as exc_info:
            LLMRegistry.get("fake-model")
        error_msg = str(exc_info.value)
        assert "gpt-5-mini" in error_msg


class TestLLMRegistryGetAllNames:
    """Tests for LLMRegistry.get_all_names()."""

    def test_returns_list_of_strings(self):
        names = LLMRegistry.get_all_names()
        assert isinstance(names, list)
        assert all(isinstance(n, str) for n in names)

    def test_contains_expected_models(self):
        names = LLMRegistry.get_all_names()
        assert "gpt-5-mini" in names
        assert "gpt-5" in names

    def test_order_matches_llms_list(self):
        names = LLMRegistry.get_all_names()
        assert names == [entry["name"] for entry in LLMRegistry.LLMS]


class TestLLMRegistryGetModelAtIndex:
    """Tests for LLMRegistry.get_model_at_index()."""

    def test_valid_index(self):
        entry = LLMRegistry.get_model_at_index(0)
        assert "name" in entry
        assert "llm" in entry

    def test_out_of_bounds_wraps_to_first(self):
        entry = LLMRegistry.get_model_at_index(999)
        assert entry == LLMRegistry.LLMS[0]

    def test_negative_index_wraps_to_first(self):
        entry = LLMRegistry.get_model_at_index(-1)
        assert entry == LLMRegistry.LLMS[0]
