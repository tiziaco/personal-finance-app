"""Tests for app.agents.chatbot.title — the conversation title."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.agents.chatbot.title import TITLE_MAX_LENGTH, clean_title, generate_title

pytestmark = pytest.mark.unit


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


def _fake_llm(content):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    return llm


async def test_generate_title_uses_a_tool_free_client_and_cleans_the_answer():
    llm = _fake_llm('"Grocery spending in May"')
    with patch("app.agents.chatbot.title.LLMRegistry.get", return_value=llm) as get:
        title = await generate_title("How much on groceries in May?", "You spent 312 EUR.", "openai/gpt-5-mini")

    get.assert_called_once_with("openai/gpt-5-mini")
    assert title == "Grocery spending in May"
    prompt = llm.ainvoke.call_args.args[0]
    assert "How much on groceries in May?" in prompt[-1].content


async def test_generate_title_truncates_long_inputs():
    llm = _fake_llm("Long chat")
    with patch("app.agents.chatbot.title.LLMRegistry.get", return_value=llm):
        await generate_title("u" * 5000, "r" * 5000, "openai/gpt-5-mini")
    assert len(llm.ainvoke.call_args.args[0][-1].content) < 2500


async def test_generate_title_flattens_structured_content():
    llm = _fake_llm([{"type": "reasoning", "id": "r"}, {"type": "text", "text": "Car savings plan"}])
    with patch("app.agents.chatbot.title.LLMRegistry.get", return_value=llm):
        assert await generate_title("a", "b", "openai/gpt-5-mini") == "Car savings plan"


async def test_empty_title_raises():
    with patch("app.agents.chatbot.title.LLMRegistry.get", return_value=_fake_llm('  ""  ')):
        with pytest.raises(ValueError):
            await generate_title("a", "b", "openai/gpt-5-mini")
