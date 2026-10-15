"""The chat message exchanged with an agent — the shape every agent's history uses."""

from typing import (
    Literal,
)

from pydantic import (
    BaseModel,
    Field,
)


class Message(BaseModel):
    """One message in an agent's history.

    Output shape only. The rules on what a user may send (length, script tags,
    null bytes) live on `ChatRequest`: applied here they also judged the
    assistant's replies, so a long answer, or one quoting `<script>` in a code
    block, turned the history route into a 500.

    Attributes:
        role: The role of the message sender (user, assistant or system).
        content: The content of the message.
    """

    model_config = {"extra": "ignore"}

    role: Literal["user", "assistant", "system"] = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The content of the message", min_length=1)
