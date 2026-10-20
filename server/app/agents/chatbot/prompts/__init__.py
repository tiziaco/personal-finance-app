"""Prompts for the chatbot agent."""

from pathlib import Path

_SYSTEM_PROMPT = Path(__file__).with_name("system.md")


def load_system_prompt() -> str:
    """The static system prompt.

    No date and no memory: those change every turn and live in the turn context
    message, after the history, so the provider can cache this prefix.
    """
    return _SYSTEM_PROMPT.read_text()
