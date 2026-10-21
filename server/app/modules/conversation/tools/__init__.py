"""The chat's tools, a feature sub-package of conversation (docs/architecture/server.md §2).

Seven read-only `StructuredTool`s over one `AnalyticsHistory` per turn, and the turn's preamble. They
read the user's money through the analytics and transaction package roots; the conversation core never
imports this package (R10). `chat_tools()` and `chat_preamble` are what the agent is built from.
"""

from langchain_core.tools import BaseTool

from app.modules.conversation.tools.analytics import analytics_tools
from app.modules.conversation.tools.periods import preamble
from app.modules.conversation.tools.search import search_tool

chat_preamble = preamble


def chat_tools() -> list[BaseTool]:
    """The chat's tools, in the order the model is offered them."""
    return [*analytics_tools(), search_tool()]


__all__ = ["chat_preamble", "chat_tools"]
