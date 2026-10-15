"""prepare_messages trims with a real registry LLM's token counter."""

import pytest

from app.agents.graph import prepare_messages
from app.agents.messages import Message
from app.integrations.llm.service import LLMRegistry

pytestmark = pytest.mark.unit


def test_prepare_messages_puts_system_prompt_first_with_registry_llm():
    llm = LLMRegistry.get(LLMRegistry.get_all_names()[0])
    history = [Message(role="user", content="hello")]

    result = prepare_messages(history, llm, "be helpful")

    assert result[0].role == "system"
    assert result[0].content == "be helpful"
    assert [m.content for m in result[1:]] == ["hello"]
