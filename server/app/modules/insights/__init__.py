"""Insights — the AI-written insights about a user's spending.

This is the public surface. Another module imports from here and nowhere
deeper (docs/architecture/server.md, R1).
"""

from app.modules.insights.router import router
from app.modules.insights.service import insights_service

__all__ = ["insights_service", "router"]

# @events.on is a module-level side effect: importing the root is what subscribes.
from app.modules.insights import handlers  # noqa: E402, F401
