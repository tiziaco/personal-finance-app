"""State schema for the chatbot agent."""

from typing import NotRequired

from langchain.agents import AgentState


class ChatState(AgentState):
    """The chat agent's state: `messages` plus what its middleware keep between steps.

    Every key is optional, so a checkpoint written before a key existed still loads;
    readers use `state.get(key, default)`.
    """

    long_term_memory: NotRequired[str]
    stopped: NotRequired[dict[str, str]]
    summary: NotRequired[str]
    summary_through: NotRequired[str | None]
