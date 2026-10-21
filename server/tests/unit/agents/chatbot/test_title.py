"""Tests for app.agents.chatbot.title — the conversation title."""

from unittest.mock import patch

import pytest
from uuid_utils.compat import uuid7

from app.agents.chatbot.title import TITLE_MAX_LENGTH, clean_title, generate_title
from tests.unit.agents.fakes import FakeModel

pytestmark = pytest.mark.unit

CONVERSATION_ID = uuid7()
USER_ID = uuid7()


@pytest.fixture(autouse=True)
def no_langfuse_client():
    with patch("app.agents.core.observability.CallbackHandler"):
        yield


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('"Monthly grocery budget"', "Monthly grocery budget"),
        ("“Rent vs. mortgage”", "Rent vs. mortgage"),
        ("Saving for a car.", "Saving for a car"),
        ("  Title: Travel fund\n", "Travel fund"),
        ("Line one\nline two", "Line one line two"),
        # Each rule can expose what another strips: a quote behind punctuation,
        # a prefix behind a quote.
        ('"Budget tips".', "Budget tips"),
        ('"Title: Rent"', "Rent"),
    ],
)
def test_clean_title(raw, expected):
    assert clean_title(raw) == expected


def test_clean_title_caps_length():
    assert len(clean_title("word " * 100)) <= TITLE_MAX_LENGTH


async def test_generate_title_cleans_the_answer():
    model = FakeModel('"Grocery spending in May"')
    title = await generate_title(
        "How much on groceries in May?", "You spent 312 EUR.", CONVERSATION_ID, USER_ID, model=model
    )

    assert title == "Grocery spending in May"
    assert "How much on groceries in May?" in model.calls[0][0][-1].content


async def test_generate_title_truncates_long_inputs():
    model = FakeModel("Long chat")
    await generate_title("u" * 5000, "r" * 5000, CONVERSATION_ID, USER_ID, model=model)
    assert len(model.calls[0][0][-1].content) < 2500


async def test_generate_title_flattens_structured_content():
    model = FakeModel([{"type": "reasoning", "id": "r"}, {"type": "text", "text": "Car savings plan"}])
    assert await generate_title("a", "b", CONVERSATION_ID, USER_ID, model=model) == "Car savings plan"


async def test_an_empty_title_is_none():
    assert await generate_title("a", "b", CONVERSATION_ID, USER_ID, model=FakeModel('  ""  ')) is None


async def test_without_a_model_it_uses_the_primary_with_its_fallbacks():
    model = FakeModel("Car savings plan")
    with (
        patch("app.agents.chatbot.title.chat_model"),
        patch("app.agents.chatbot.title.with_fallbacks", return_value=model),
    ):
        assert await generate_title("a", "b", CONVERSATION_ID, USER_ID) == "Car savings plan"


async def test_generate_title_is_traced_to_its_conversation():
    model = FakeModel("Car savings plan")
    await generate_title("a", "b", CONVERSATION_ID, USER_ID, model=model)

    config = model.calls[0][1]
    assert config["callbacks"]
    assert config["metadata"]["langfuse_session_id"] == str(CONVERSATION_ID)
    assert config["metadata"]["langfuse_user_id"] == str(USER_ID)
