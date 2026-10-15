"""Tests for app.core.config — environment resolution and settings properties."""

import pytest
from pydantic import ValidationError

from app.core.config import AuthSettings, Environment, EvaluationSettings, LLMSettings, MemorySettings, get_environment

pytestmark = pytest.mark.unit


class TestGetEnvironment:
    """Tests for get_environment() function."""

    @pytest.mark.parametrize(
        "env_value,expected",
        [
            ("production", Environment.PRODUCTION),
            ("prod", Environment.PRODUCTION),
            ("staging", Environment.STAGING),
            ("stage", Environment.STAGING),
            ("test", Environment.TEST),
            ("development", Environment.DEVELOPMENT),
            ("dev", Environment.DEVELOPMENT),
            ("PRODUCTION", Environment.PRODUCTION),  # case insensitive
            ("Test", Environment.TEST),
        ],
        ids=["production", "prod", "staging", "stage", "test", "development", "dev", "uppercase", "mixed-case"],
    )
    def test_environment_resolution(self, monkeypatch, env_value, expected):
        monkeypatch.setenv("APP_ENV", env_value)
        assert get_environment() == expected

    def test_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("APP_ENV", raising=False)
        assert get_environment() == Environment.DEVELOPMENT

    @pytest.mark.parametrize("env_value", ["unknown", "production ", "prd", ""])
    def test_unrecognised_value_raises(self, monkeypatch, env_value):
        """A typo must not silently resolve to development."""
        monkeypatch.setenv("APP_ENV", env_value)
        with pytest.raises(ValueError, match="APP_ENV"):
            get_environment()


class TestAuthSettings:
    """Tests for AuthSettings derived properties."""

    def test_jwks_url_derived_from_issuer(self):
        auth = AuthSettings(ISSUER="https://clerk.example.com")
        assert auth.jwks_url == "https://clerk.example.com/.well-known/jwks.json"

    def test_jwks_url_empty_issuer(self):
        auth = AuthSettings(ISSUER="")
        assert auth.jwks_url == "/.well-known/jwks.json"


class TestEnvironmentEnum:
    """Tests for Environment enum values."""

    def test_enum_values(self):
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.STAGING.value == "staging"
        assert Environment.PRODUCTION.value == "production"
        assert Environment.TEST.value == "test"

    def test_enum_is_string(self):
        assert isinstance(Environment.PRODUCTION, str)
        assert Environment.PRODUCTION == "production"


def test_evaluation_key_falls_back_to_the_openrouter_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.delenv("EVALUATION_API_KEY", raising=False)
    assert EvaluationSettings().API_KEY.get_secret_value() == "or-key"


class TestOpenRouterModelIds:
    """Every model id names its provider: an env file written for the OpenAI API fails at startup."""

    @pytest.mark.parametrize(
        "build",
        [
            lambda: LLMSettings(DEFAULT_LLM_MODEL="gpt-4o-mini"),
            lambda: MemorySettings(MODEL="gpt-5-nano"),
            lambda: MemorySettings(EMBEDDER_MODEL="text-embedding-3-small"),
            lambda: EvaluationSettings(LLM="gpt-5"),
        ],
        ids=["chat", "memory", "embedder", "evaluation"],
    )
    def test_an_unprefixed_model_id_fails(self, build):
        with pytest.raises(ValidationError, match="provider/model"):
            build()

    def test_a_prefixed_model_id_passes(self):
        assert LLMSettings(DEFAULT_LLM_MODEL="openai/gpt-4o-mini").DEFAULT_LLM_MODEL == "openai/gpt-4o-mini"
