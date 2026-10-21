"""Prompts for the chatbot agent."""

from pathlib import Path

_SYSTEM_PROMPT = Path(__file__).with_name("system.md")
_SUMMARY_PROMPT = Path(__file__).with_name("summary.md")


def load_system_prompt() -> str:
    """The static system prompt.

    No date and no memory: those change every turn and live in the turn context
    message, after the history, so the provider can cache this prefix.
    """
    return _SYSTEM_PROMPT.read_text()


def load_summary_prompt() -> str:
    """The instructions for the model that folds earlier turns into the running summary."""
    return _SUMMARY_PROMPT.read_text()
