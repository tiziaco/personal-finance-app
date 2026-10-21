"""What every chat tool shares: the argument base, the turn's history and the tool factory.

A tool declares `runtime: ToolRuntime[TurnContext]` and reads the user from `runtime.context`; the
user is never one of the model's arguments.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Optional

from langchain.tools import ToolRuntime
from langchain_core.tools import InjectedToolArg, StructuredTool
from pydantic import BaseModel, ConfigDict, Field, SkipValidation

from app.agents.chatbot.context import TurnContext
from app.modules.analytics import AnalyticsHistory, analytics_service
from app.modules.transaction import CATEGORIES

NO_TRANSACTIONS = "The user has no transactions yet."
CATEGORY_NAMES = dict(CATEGORIES)


class ToolArgs(BaseModel):
    """The base of every tool's arguments: the model's fields, and the injected runtime slot.

    The tool node injects `runtime` into the call's arguments and an explicit schema rejects what it
    does not declare, so the slot is declared: injected (left out of the schema the model sees),
    excluded from dumps, and optional so the arguments validate without a runtime.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    runtime: Annotated[SkipValidation[Optional[ToolRuntime]], InjectedToolArg] = Field(None, exclude=True)


async def _load_history(ctx: TurnContext) -> AnalyticsHistory:
    async with ctx.session_factory() as session:
        return await analytics_service.history(session, ctx.user_id)


async def turn_history(ctx: TurnContext) -> AnalyticsHistory:
    """The signed-in user's history, loaded once per turn and shared by the turn's tool calls.

    The slot holds the load itself, not its result, so tool calls running concurrently
    wait on the one load instead of each starting their own.
    """
    if ctx.history is None:
        ctx.history = asyncio.ensure_future(_load_history(ctx))
    return await ctx.history


def chat_tool(
    coroutine: Callable[..., Awaitable[Any]], *, name: str, title: str, description: str, args_schema: type[ToolArgs]
) -> StructuredTool:
    """A chat tool: it returns `(content, artifact)`, the model's text and the UI's display."""
    return StructuredTool.from_function(
        coroutine=coroutine,
        name=name,
        description=description,
        args_schema=args_schema,
        response_format="content_and_artifact",
        metadata={"title": title},
    )
