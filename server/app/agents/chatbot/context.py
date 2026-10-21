"""The chat agent's context schema: what one turn hands the graph besides its messages."""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker


@dataclass
class TurnContext:
    """What a tool may use during one chat turn; built once per turn by the route.

    The user is never a tool argument: tools read `user_id` from here, so no
    wording of a question can reach another user's data. `history` is the
    per-turn load of the user's analytics history: a `Future` the chat's tools
    set and share, typed `Any` because `agents` does not know the type.
    """

    user_id: uuid.UUID
    session_factory: async_sessionmaker
    history: Any = None
