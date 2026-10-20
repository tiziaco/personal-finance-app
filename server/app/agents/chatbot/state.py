"""State schema for the chatbot agent."""

from typing import Annotated

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
