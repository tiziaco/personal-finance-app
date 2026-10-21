"""State schema for the chatbot agent."""

from typing import Annotated, NotRequired

from langchain.agents import AgentState
from langgraph.graph.message import add_messages
from pydantic import (
    BaseModel,
    Field,
)


class GraphState(BaseModel):
    """State definition for the chatbot agent workflow."""

    messages: Annotated[list, add_messages] = Field(
        default_factory=list, description="The messages in the conversation"
    )
    long_term_memory: str = Field(default="", description="The long term memory of the conversation")
    turn_steps: int = Field(
        default=0, description="Model calls with tool calls so far this turn; the turn's input resets it"
    )
    stopped: dict[str, str] = Field(
        default_factory=dict,
        description="Final assistant message id -> why the server ended its turn: step_limit or repeated_call",
    )


class ChatState(AgentState):
    """The chat agent's state: `messages` plus what its middleware keep between steps.

    Every key is optional, so a checkpoint written before a key existed still loads;
    readers use `state.get(key, default)`.
    """

    long_term_memory: NotRequired[str]
    stopped: NotRequired[dict[str, str]]
    summary: NotRequired[str]
    summary_through: NotRequired[str | None]
