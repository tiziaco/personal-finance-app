"""The contract between the chatbot loop and the tools it runs.

The agent package knows nothing finance-specific: a module builds a `Toolkit` and
injects it at startup (`initialize_agents`). The loop validates a call's arguments
against `AgentTool.args_schema`, hands the tool a per-turn `TurnContext`, and
carries the `ToolOutcome` back: `content` for the model, `display` for the UI.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.agents.chatbot.context import TurnContext


class ToolArgumentError(Exception):
    """A tool refuses its arguments, with a message written for the model.

    The text goes back to the model verbatim as that call's result so it can
    correct itself ("category must be one of ..."), unlike any other exception,
    whose text never enters a ToolMessage.
    """


class _DisplayModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


SummaryKind = Literal["count", "text", "total", "share", "rate", "weekendBias"]
"""How the web shows a summary figure, as the analytics page shows the same one.

`total` is an amount as a decimal string, unsigned under a label that says its direction.
`share` and `rate` are percents, a rate coloured good or bad; `weekendBias` is the percent
a weekend day costs over a weekday, worded as a sentence.
"""

ColumnKind = Literal["text", "count", "date", "total", "net", "transaction", "share", "rate", "change"]
"""How the web shows a table cell. Amounts are decimal strings: a `total` unsigned, a `net`
signed and coloured, a `transaction` signed with income coloured. A `change` is a percent
change in spending, "new" when there was nothing before, or null with no period to compare.
"""


class SummaryItem(_DisplayModel):
    """One figure in a tool row's one-line summary, e.g. a count, an amount or a share."""

    kind: SummaryKind
    value: float | int | str
    label: str | None = None


class TableColumn(_DisplayModel):
    """A column of a tool result's table: the row key, its header and how to format it."""

    key: str
    label: str
    kind: ColumnKind


class ToolTable(_DisplayModel):
    """The figures behind a tool result, as values the client formats by column kind; bounded for the UI."""

    columns: list[TableColumn]
    rows: list[dict[str, str | float | int | None]]


class ToolDisplay(_DisplayModel):
    """What the chat UI shows for one tool call: a title, the period covered, a summary and an optional table."""

    title: str
    period: str | None
    summary: list[SummaryItem]
    table: ToolTable | None


@dataclass
class ToolOutcome:
    """A tool's result: `content` is what the model reads, `display` what the user sees."""

    content: str
    display: ToolDisplay


@dataclass
class AgentTool:
    """One tool the model may call.

    `args_schema` is the whole argument contract: the loop validates against it
    before `run` is reached, so `run` receives a valid instance.
    """

    name: str
    title: str
    description: str
    args_schema: type[BaseModel]
    run: Callable[[Any, TurnContext], Awaitable[ToolOutcome]]

    def as_schema(self) -> dict:
        """The OpenAI-style tool schema, as `bind_tools` accepts it."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }


async def _no_preamble(_ctx: TurnContext) -> str:
    return ""


@dataclass
class Toolkit:
    """The tools injected into an agent, plus per-turn text for its system prompt."""

    tools: list[AgentTool]
    preamble: Callable[[TurnContext], Awaitable[str]]

    @classmethod
    def empty(cls) -> "Toolkit":
        """A toolkit with no tools and no preamble."""
        return cls(tools=[], preamble=_no_preamble)
