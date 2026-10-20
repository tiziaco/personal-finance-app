"""The chat's finance tools, a feature sub-package of conversation (docs/architecture/server.md §2).

It reads the user's money through the analytics and transaction package roots; the
conversation core never imports it (R10). The module root re-exports `finance_toolkit`.
"""

from app.modules.conversation.finance.service import finance_toolkit

__all__ = ["finance_toolkit"]
